import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_async_session
from app.schema.database import EventReminder
from app.tasks.mail_tasks import send_due_event_reminder, send_verification_email

logger = logging.getLogger(__name__)


def queue_verification_email(
    background_tasks: BackgroundTasks,
    *, recipient: str, recipient_name: str, verification_url: str,
) -> None:
    try:
        background_tasks.add_task(send_verification_email, recipient, recipient_name, verification_url)
    except Exception:
        logger.exception("Unable to queue verification email")


def queue_interest_notification(
    background_tasks: BackgroundTasks,
    *,
    recipient: str,
    recipient_name: str,
    company_name: str,
    company_process: str,
    company_location: str,
    company_date: datetime,
) -> None:
    try:
        background_tasks.add_task(
            send_interest_notification,
            recipient,
            recipient_name,
            company_name,
            company_process,
            company_location,
            company_date.isoformat(),
        )
    except Exception:
        logger.exception("Unable to queue interest notification")


async def queue_event_reminder(session: AsyncSession, company_id: int, company_date: datetime) -> None:
    """Persist a reminder so it remains available after process restarts or sleep."""
    if company_date.tzinfo is None:
        company_date = company_date.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    event_at = company_date.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    scheduled_at = event_at - timedelta(hours=1)
    day_before_scheduled_at = event_at - timedelta(days=1)
    reminder = await session.scalar(select(EventReminder).where(EventReminder.company_id == company_id))
    if reminder is None:
        reminder = EventReminder(company_id=company_id, scheduled_at=scheduled_at, day_before_scheduled_at=day_before_scheduled_at)
        session.add(reminder)
    else:
        reminder.scheduled_at = scheduled_at
        reminder.sent_at = None
        reminder.claimed_at = None
    reminder.day_before_sent_at = None
    reminder.day_before_claimed_at = None
    reminder.day_before_scheduled_at = day_before_scheduled_at
    if event_at <= now:
        reminder.sent_at = now
        reminder.day_before_sent_at = now
    elif event_at <= now + timedelta(hours=1):
        # A drive added within its one-hour window should notify immediately.
        reminder.scheduled_at = now
    await session.commit()


async def schedule_due_reminders(
    background_tasks: BackgroundTasks,
    session: AsyncSession,
) -> None:
    """Claim due reminders and run them after this request returns."""
    now = datetime.now(timezone.utc)
    stale_claim = now - timedelta(minutes=10)
    reminders = (await session.scalars(
        select(EventReminder).where(
            EventReminder.sent_at.is_(None),
            EventReminder.scheduled_at <= now,
            or_(EventReminder.claimed_at.is_(None), EventReminder.claimed_at < stale_claim),
        ).with_for_update(skip_locked=True)
    )).all()
    for reminder in reminders:
        reminder.claimed_at = now
    if reminders:
        await session.commit()
    company_ids = [reminder.company_id for reminder in reminders]
    for company_id in company_ids:
        background_tasks.add_task(send_due_event_reminder, company_id, "hour")

    day_reminders = (await session.scalars(
        select(EventReminder).where(
            EventReminder.day_before_sent_at.is_(None),
            EventReminder.day_before_scheduled_at <= now,
            or_(EventReminder.day_before_claimed_at.is_(None), EventReminder.day_before_claimed_at < stale_claim),
        ).with_for_update(skip_locked=True)
    )).all()
    for reminder in day_reminders:
        reminder.day_before_claimed_at = now
    if day_reminders:
        await session.commit()
    for reminder in day_reminders:
        background_tasks.add_task(send_due_event_reminder, reminder.company_id, "day")


async def due_reminders_dependency(background_tasks: BackgroundTasks) -> None:
    async for session in get_async_session():
        await schedule_due_reminders(background_tasks, session)
