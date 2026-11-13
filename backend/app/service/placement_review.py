import re
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schema.database import Company, PendingPlacementOpportunity, Process, ProcessedEmail, Role
from app.schema.models import PendingOpportunityRead, PendingOpportunityUpdate, PossibleDuplicate
from app.service.mail_services import queue_event_reminder


def require_spc(user) -> None:
    if user.role != Role.spc:
        raise HTTPException(status_code=403, detail="Only SPC users can review placement opportunities")


def _normalized_company_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]", "", value.casefold())
    suffixes = ("privatelimited", "incorporated", "limited", "pvt", "ltd", "inc", "llc")
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if normalized.endswith(suffix) and len(normalized) > len(suffix) + 2:
                normalized = normalized[:-len(suffix)]
                changed = True
                break
    return normalized


def _event_keys(item: PendingPlacementOpportunity) -> set[tuple[str, date]]:
    events: set[tuple[str, date]] = set()
    for process, value in (
        ("online_assesment", item.assessment_date),
        ("group_discussion", item.group_discussion_date),
        ("interview", item.interview_date),
    ):
        if value:
            events.add((process, value.date()))
    for value in item.interview_dates or []:
        try:
            events.add(("interview", date.fromisoformat(value[:10])))
        except (TypeError, ValueError):
            continue
    if not events:
        fallback = item.department_submission_date or item.application_deadline
        if fallback:
            events.add(("send_mail", fallback.date()))
    return events


async def get_duplicate_candidates(session: AsyncSession):
    pending = (await session.scalars(
        select(PendingPlacementOpportunity)
        .where(PendingPlacementOpportunity.review_status == "PENDING")
        .order_by(PendingPlacementOpportunity.created_at.desc())
        .limit(200)
    )).all()
    published = (await session.scalars(select(Company).order_by(Company.id.desc()).limit(2000))).all()
    return pending, published


async def serialize_opportunity(
    session: AsyncSession,
    item: PendingPlacementOpportunity,
    duplicate_candidates=None,
) -> PendingOpportunityRead:
    source = await session.get(ProcessedEmail, item.source_email_id) if item.source_email_id else None
    if duplicate_candidates is None:
        duplicate_candidates = await get_duplicate_candidates(session)
    pending_candidates, published_candidates = duplicate_candidates
    name_key = _normalized_company_name(item.company_name)
    event_keys = _event_keys(item)
    duplicates: list[PossibleDuplicate] = []
    for other in pending_candidates:
        if other.id == item.id or _normalized_company_name(other.company_name) != name_key:
            continue
        common_events = event_keys & _event_keys(other)
        for process, event_date in sorted(common_events):
            duplicates.append(PossibleDuplicate(
                record_type="PENDING",
                record_id=other.id,
                company_name=other.company_name,
                process=process,
                event_date=datetime.combine(event_date, datetime.min.time(), tzinfo=timezone.utc),
            ))
    for company in published_candidates:
        if _normalized_company_name(company.name) != name_key:
            continue
        process = company.process.value if hasattr(company.process, "value") else str(company.process)
        company_date = company.date.date()
        if (process, company_date) in event_keys:
            duplicates.append(PossibleDuplicate(
                record_type="PUBLISHED",
                record_id=company.id,
                company_name=company.name,
                process=process,
                event_date=company.date,
            ))
    duplicates.sort(key=lambda match: (match.record_type, match.record_id, match.process, match.event_date))
    return PendingOpportunityRead(
        **{
            key: getattr(item, key)
            for key in PendingOpportunityRead.model_fields
            if key not in {"source_subject", "source_sender", "source_link", "source_attachments", "possible_duplicates"}
        },
        source_subject=source.subject if source else None,
        source_sender=source.sender if source else None,
        source_link=source.source_link if source else None,
        source_attachments=(source.extracted_data or {}).get("attachments", []) if source else [],
        possible_duplicates=duplicates,
    )


async def approve_opportunity(session: AsyncSession, item: PendingPlacementOpportunity, user) -> PendingPlacementOpportunity:
    require_spc(user)
    if item.review_status != "PENDING":
        raise HTTPException(status_code=409, detail="This opportunity has already been reviewed")
    event_date = item.assessment_date or item.group_discussion_date or item.interview_date or item.department_submission_date
    process = Process.send_mail
    if item.assessment_date is not None:
        process = Process.online_assesment
    elif item.group_discussion_date is not None:
        process = Process.group_discussion
    elif item.interview_date is not None:
        process = Process.interview
    if event_date is None:
        event_date = item.application_deadline or datetime.now(timezone.utc)

    company = Company(
        name=item.company_name,
        process=process,
        location=item.location or "Not specified",
        date=event_date,
        # The legacy company row supports one batch; use a sentinel so unknown or
        # multi-batch email opportunities are not silently treated as 2027-only.
        year_of_passing=(item.eligible_batches[0] if len(item.eligible_batches) == 1 else 0),
        considered=False,
    )
    session.add(company)
    await session.flush()
    await queue_event_reminder(session, company.id, company.date)
    item.published_company_id = company.id
    item.review_status = "APPROVED"
    item.reviewed_by = user.id
    item.reviewed_at = datetime.now(timezone.utc)
    item.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(item)
    return item


async def update_pending(session: AsyncSession, item: PendingPlacementOpportunity, payload: PendingOpportunityUpdate) -> None:
    if item.review_status != "PENDING":
        raise HTTPException(status_code=409, detail="Only pending opportunities can be edited")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    item.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(item)
