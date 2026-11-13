from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from sqlalchemy import select

from app.database.database import SessionDep
from app.schema.database import Company, Interested, PendingPlacementOpportunity, ProcessedEmail, User
from app.schema.models import OpportunityReject, PendingOpportunityRead, PendingOpportunityUpdate
from app.service.placement_review import (
    approve_opportunity,
    get_duplicate_candidates,
    require_spc,
    serialize_opportunity,
    update_pending,
)
from app.service.mail_services import notify_spcs_company_added_background
from app.service.user_services import CurrentUserDep

router = APIRouter(prefix="/api/admin/placement/pending", tags=["Placement review"])


@router.get("/", response_model=list[PendingOpportunityRead])
async def list_pending(
    session: SessionDep,
    user: CurrentUserDep,
    status: Annotated[str, Query(pattern="^(PENDING|APPROVED|REJECTED|ALL)$")] = "PENDING",
):
    require_spc(user)
    query = select(PendingPlacementOpportunity).order_by(PendingPlacementOpportunity.created_at.desc())
    if status != "ALL":
        query = query.where(PendingPlacementOpportunity.review_status == status)
    items = (await session.scalars(query.limit(200))).all()
    candidates = await get_duplicate_candidates(session)
    return [await serialize_opportunity(session, item, candidates) for item in items]


@router.get("/{opportunity_id}", response_model=PendingOpportunityRead)
async def get_pending(opportunity_id: int, session: SessionDep, user: CurrentUserDep):
    require_spc(user)
    item = await session.get(PendingPlacementOpportunity, opportunity_id)
    if not item:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return await serialize_opportunity(session, item)


@router.patch("/{opportunity_id}", response_model=PendingOpportunityRead)
async def edit_pending(opportunity_id: int, payload: PendingOpportunityUpdate, session: SessionDep, user: CurrentUserDep):
    require_spc(user)
    item = await session.get(PendingPlacementOpportunity, opportunity_id)
    if not item:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    await update_pending(session, item, payload)
    from app.service.eligibility import assess_mca_eligibility
    result = assess_mca_eligibility(item.eligible_courses, branches=item.eligible_branches, eligible_batches=item.eligible_batches)
    item.eligibility_status = result.status
    item.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(item)
    return await serialize_opportunity(session, item)


@router.post("/{opportunity_id}/approve", response_model=PendingOpportunityRead)
async def approve_pending(opportunity_id: int, background_tasks: BackgroundTasks, session: SessionDep, user: CurrentUserDep):
    item = await session.get(PendingPlacementOpportunity, opportunity_id)
    if not item:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    await approve_opportunity(session, item, user)
    company_id = item.published_company_id
    company = await session.get(Company, company_id)
    existing_user_ids = set((await session.scalars(select(Interested.user_id).where(Interested.company_id == company_id))).all())
    users = (await session.scalars(select(User))).all()
    session.add_all(Interested(user_id=person.id, company_id=company_id, interested=False) for person in users if person.id not in existing_user_ids)
    await session.commit()
    background_tasks.add_task(
        notify_spcs_company_added_background,
        [(person.email, person.name) for person in users if person.role.value == "SPC" and person.id != user.id],
        company.name,
        company.process.value,
        company.location,
        company.date.isoformat(),
    )
    await session.refresh(item)
    return await serialize_opportunity(session, item)


@router.post("/{opportunity_id}/reject", response_model=PendingOpportunityRead)
async def reject_pending(opportunity_id: int, payload: OpportunityReject, session: SessionDep, user: CurrentUserDep):
    require_spc(user)
    item = await session.get(PendingPlacementOpportunity, opportunity_id)
    if not item:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if item.review_status != "PENDING":
        raise HTTPException(status_code=409, detail="This opportunity has already been reviewed")
    item.review_status = "REJECTED"
    item.reviewed_by = user.id
    item.reviewed_at = datetime.now(timezone.utc)
    item.updated_at = datetime.now(timezone.utc)
    item.rejection_reason = payload.reason.strip()
    await session.commit()
    await session.refresh(item)
    return await serialize_opportunity(session, item)

