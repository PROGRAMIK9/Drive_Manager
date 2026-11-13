"""Durable Gmail notification queue and placement-email processing pipeline."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config.config import gmail_settings
from app.config.config import app_settings
from app.database.database import engine
from app.schema.database import GmailIntegration, GmailNotification, PendingPlacementOpportunity, ProcessedEmail, Role, User
from app.service.eligibility import assess_mca_eligibility
from app.service.email_sender import send_template_email
from app.service.gmail_sync import (
    fetch_message,
    get_access_token,
    list_history,
    list_messages_since,
    start_gmail_watch,
    store_fetched_message,
)
from app.service.placement_extraction import extract_placement_email, parse_extracted_date

logger = logging.getLogger(__name__)
session_factory = async_sessionmaker(engine, expire_on_commit=False)
_worker_lock = asyncio.Lock()


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


async def enqueue_gmail_notification(
    session,
    *,
    pubsub_message_id: str,
    email_address: str,
    history_id: str,
) -> bool:
    existing = await session.scalar(
        select(GmailNotification).where(GmailNotification.pubsub_message_id == pubsub_message_id)
    )
    if existing:
        if existing.processing_status in {"FAILED", "RECEIVED"}:
            existing.processing_status = "RECEIVED"
            existing.next_attempt_at = datetime.now(timezone.utc)
            existing.last_error = None
            existing.history_id = history_id
            await session.commit()
        return False
    session.add(GmailNotification(
        pubsub_message_id=pubsub_message_id,
        email_address=email_address,
        history_id=history_id,
        processing_status="RECEIVED",
        next_attempt_at=datetime.now(timezone.utc),
    ))
    try:
        await session.commit()
        return True
    except IntegrityError:
        await session.rollback()
        return False


async def _extract_and_queue(session, email_row: ProcessedEmail) -> str:
    if email_row.processing_status == "IGNORED_SENDER":
        return "ignored_sender"
    if email_row.processing_status in {"PROCESSED", "IGNORED_NON_PLACEMENT"}:
        return "already_processed"

    body = str((email_row.extracted_data or {}).get("body", ""))
    result = await extract_placement_email(
        subject=email_row.subject or "",
        sender=email_row.sender or "",
        received_at=email_row.received_at,
        body=body,
    )
    email_row.extracted_data = {**(email_row.extracted_data or {}), "placement_extraction": result}
    email_row.classification = "PLACEMENT_OPPORTUNITY" if result["is_placement_opportunity"] else "NOT_PLACEMENT"
    email_row.processing_error = None
    email_row.updated_at = datetime.now(timezone.utc)

    if not result["is_placement_opportunity"]:
        email_row.processing_status = "IGNORED_NON_PLACEMENT"
        await session.commit()
        return "not_placement"

    company_name = str(result.get("company_name") or "").strip()
    missing = list(result.get("missing_information") or [])
    if not company_name:
        company_name = "Company name needs SPC review"
        missing.append("company_name")

    existing = await session.scalar(
        select(PendingPlacementOpportunity).where(PendingPlacementOpportunity.source_email_id == email_row.id)
    )
    created_pending = existing is None
    if created_pending:
        eligibility = assess_mca_eligibility(
            result.get("eligible_courses"),
            excluded_courses=result.get("excluded_courses"),
            branches=result.get("eligible_branches"),
            excluded_branches=result.get("excluded_branches"),
            eligible_batches=result.get("eligible_batches"),
        )
        interview_dates = [date for date in result.get("interview_dates", []) if parse_extracted_date(date)]
        interview_dates.sort()
        if not result.get("interview_date") and interview_dates:
            result["interview_date"] = interview_dates[0]
        session.add(PendingPlacementOpportunity(
            company_name=company_name,
            job_title=result.get("job_title"),
            description=result.get("description"),
            opportunity_type=result.get("opportunity_type"),
            eligible_courses=result.get("eligible_courses", []),
            eligible_branches=result.get("eligible_branches", []),
            eligible_batches=result.get("eligible_batches", []),
            minimum_cgpa=result.get("minimum_cgpa"),
            backlog_allowed=result.get("backlog_allowed"),
            maximum_backlogs=result.get("maximum_backlogs"),
            location=result.get("location"),
            compensation=result.get("compensation"),
            internship_duration=result.get("internship_duration"),
            application_deadline=parse_extracted_date(result.get("application_deadline")),
            department_submission_date=parse_extracted_date(result.get("department_submission_date")),
            assessment_date=parse_extracted_date(result.get("assessment_date")),
            group_discussion_date=parse_extracted_date(result.get("group_discussion_date")),
            interview_date=parse_extracted_date(result.get("interview_date")),
            interview_dates=interview_dates,
            application_link=result.get("application_link"),
            eligibility_status=eligibility.status,
            ai_confidence=result.get("confidence"),
            missing_information=list(dict.fromkeys(missing)),
            source_email_id=email_row.id,
            review_status="PENDING",
        ))
    email_row.processing_status = "PROCESSED"
    await session.commit()
    if created_pending:
        coordinators = (await session.scalars(select(User).where(User.role == Role.spc))).all()
        review_url = f"{app_settings.FRONTEND_URL.rstrip('/')}/"
        for coordinator in coordinators:
            try:
                await send_template_email(
                    recipient=coordinator.email,
                    subject=f"Placement email needs SPC review: {company_name}",
                    template_name="placement_review.html",
                    context={
                        "recipient_name": coordinator.name,
                        "company_name": company_name,
                        "email_subject": email_row.subject or "(no subject)",
                        "email_sender": email_row.sender or "Unknown sender",
                        "review_url": review_url,
                    },
                )
            except Exception:
                logger.exception("Unable to notify SPC %s about pending opportunity %s", coordinator.id, company_name)
    return "placement"


async def _process_message_ids(session, access_token: str, message_ids: list[str]) -> dict[str, int]:
    counts = {"fetched": 0, "accepted_sender": 0, "ignored_sender": 0, "placement_opportunities": 0}
    for message_id in message_ids:
        details = await fetch_message(access_token, message_id)
        email_row = await store_fetched_message(session, details)
        counts["fetched"] += 1
        if email_row.processing_status == "IGNORED_SENDER":
            counts["ignored_sender"] += 1
            continue
        counts["accepted_sender"] += 1
        outcome = await _extract_and_queue(session, email_row)
        if outcome == "placement":
            counts["placement_opportunities"] += 1
    return counts


async def sync_mailbox_history(session, integration: GmailIntegration) -> dict[str, int | str]:
    if not integration.last_history_id:
        watch = await start_gmail_watch(integration, await get_access_token(integration))
        await session.commit()
        return {"fetched": 0, "accepted_sender": 0, "ignored_sender": 0, "placement_opportunities": 0, "history_id": str(watch.get("historyId", ""))}

    access_token = await get_access_token(integration)
    try:
        message_ids, new_history_id = await list_history(access_token, integration.last_history_id)
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        previous_sync = _aware(integration.last_sync_at) or datetime.now(timezone.utc) - timedelta(days=30)
        previous_cursor = integration.last_history_id
        watch = await start_gmail_watch(integration, access_token)
        new_history_id = str(watch.get("historyId") or previous_cursor)
        # Don't commit the new cursor until catch-up has finished; per-email
        # commits below must not make an incomplete backfill unrecoverable.
        integration.last_history_id = previous_cursor
        integration.last_sync_at = previous_sync
        message_ids = await list_messages_since(access_token, previous_sync - timedelta(minutes=2))

    counts = await _process_message_ids(session, access_token, message_ids)
    integration.last_history_id = new_history_id
    integration.last_sync_at = datetime.now(timezone.utc)
    integration.last_error = None
    integration.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return {**counts, "history_id": new_history_id}


async def _claim_notification() -> int | None:
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(minutes=15)
    async with session_factory() as session:
        query = (
            select(GmailNotification)
            .where(
                or_(
                    (GmailNotification.processing_status == "RECEIVED")
                    & (GmailNotification.next_attempt_at <= now),
                    (GmailNotification.processing_status == "FAILED")
                    & (GmailNotification.next_attempt_at <= now),
                    (GmailNotification.processing_status == "PROCESSING")
                    & (GmailNotification.processing_started_at < stale_before),
                )
            )
            .order_by(GmailNotification.received_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        item = await session.scalar(query)
        if item is None:
            return None
        item.processing_status = "PROCESSING"
        item.processing_started_at = now
        item.attempt_count += 1
        await session.commit()
        return item.id


async def _process_claimed_notification(notification_id: int) -> None:
    async with session_factory() as session:
        notification = await session.get(GmailNotification, notification_id)
        integration = await session.scalar(
            select(GmailIntegration).where(GmailIntegration.connected.is_(True))
        )
        if notification is None:
            return
        if integration is None:
            raise RuntimeError("Gmail mailbox is disconnected")
        if notification.email_address.casefold() != integration.email_address.casefold():
            notification.processing_status = "PROCESSED"
            notification.last_error = "Notification mailbox does not match the connected inbox"
            await session.commit()
            return
        await sync_mailbox_history(session, integration)
        notification.processing_status = "PROCESSED"
        notification.processing_started_at = None
        notification.last_error = None
        await session.commit()


async def _record_failure(notification_id: int, error: Exception) -> None:
    async with session_factory() as session:
        notification = await session.get(GmailNotification, notification_id)
        if notification is None:
            return
        delay_minutes = min(60, 2 ** min(notification.attempt_count, 6))
        notification.processing_status = "FAILED"
        notification.processing_started_at = None
        notification.next_attempt_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
        notification.last_error = str(error)[:2000]
        integration = await session.scalar(
            select(GmailIntegration).where(GmailIntegration.connected.is_(True))
        )
        if integration:
            integration.last_error = notification.last_error
        await session.commit()


async def _maintain_watch() -> None:
    async with session_factory() as session:
        integration = await session.scalar(select(GmailIntegration).where(GmailIntegration.connected.is_(True)))
        if integration is None:
            return
        expiration = _aware(integration.watch_expiration)
        renew_before = datetime.now(timezone.utc) + timedelta(days=1)
        if integration.last_history_id and expiration and expiration > renew_before:
            return
        try:
            token = await get_access_token(integration)
            # Process retained history before advancing the watch cursor.
            if integration.last_history_id:
                try:
                    await sync_mailbox_history(session, integration)
                except HTTPException as exc:
                    if exc.status_code != 409:
                        raise
            # Expired history recovery already starts a new watch.
            expiration = _aware(integration.watch_expiration)
            if not expiration or expiration <= renew_before:
                await start_gmail_watch(integration, token)
            integration.last_error = None
            await session.commit()
            logger.info("Gmail Watch is active until %s", integration.watch_expiration)
        except Exception as exc:
            integration_id = integration.id
            await session.rollback()
            integration = await session.get(GmailIntegration, integration_id)
            if integration:
                integration.last_error = f"Gmail watch maintenance failed: {str(exc)[:1800]}"
                await session.commit()
            raise


async def gmail_automation_loop() -> None:
    """Run inside the API process; Render Free has no free always-on worker service."""
    next_watch_maintenance = 0.0
    loop = asyncio.get_running_loop()
    while True:
        try:
            async with _worker_lock:
                if loop.time() >= next_watch_maintenance:
                    next_watch_maintenance = loop.time() + 15 * 60
                    await _maintain_watch()
                    next_watch_maintenance = loop.time() + 6 * 60 * 60
                notification_id = await _claim_notification()
                if notification_id is not None:
                    try:
                        await _process_claimed_notification(notification_id)
                    except Exception as exc:
                        logger.exception("Gmail notification processing failed id=%s", notification_id)
                        await _record_failure(notification_id, exc)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Gmail automation maintenance failed")
        await asyncio.sleep(10)


async def run_manual_mailbox_sync(session, integration: GmailIntegration) -> dict[str, int | str]:
    async with _worker_lock:
        return await sync_mailbox_history(session, integration)


async def run_manual_watch_renewal(session, integration: GmailIntegration) -> dict[str, str | None]:
    async with _worker_lock:
        token = await get_access_token(integration)
        if integration.last_history_id:
            await sync_mailbox_history(session, integration)
        result = await start_gmail_watch(integration, token)
        integration.last_error = None
        await session.commit()
        return {"history_id": integration.last_history_id, "expiration": result.get("expiration")}
