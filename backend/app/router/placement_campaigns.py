import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.database.database import SessionDep
from app.schema.database import (
    Company,
    GmailIntegration,
    GmailSendingAccount,
    GmailOAuthState,
    PlacementAnnouncementSettings,
    PlacementAttachment,
    PlacementCampaign,
    PlacementRecipient,
    PlacementRecipientList,
    PendingPlacementOpportunity,
    ProcessedEmail,
    Role,
    User,
)
from app.schema.models import AnnouncementSettingsUpdate, CampaignDraftInput, CampaignSendRequest, RecipientImport
from app.service.announcement_sender import (
    build_announcement_message,
    get_sender_access_token,
    send_gmail_message,
)
from app.service.gmail_sync import fetch_message_attachment, get_access_token
from app.service.user_services import CurrentUserDep

router = APIRouter(prefix="/api/admin/placement/announcements", tags=["Placement announcements"])
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_MESSAGE_BYTES = 20 * 1024 * 1024
ALLOWED_FILE_TYPES = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip", "application/octet-stream"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip", "application/octet-stream"},
    ".doc": {"application/msword", "application/octet-stream"},
}
DEFAULT_TEMPLATES = {
    "placement_announcement": {
        "name": "Placement announcement",
        "subject": "Placement opportunity: {company_name}",
        "body": "Hello everyone,\n\n{company_name} is recruiting students. The details are as follows:\n\nInterested students are required to fill the consent form by the stated deadline.",
    },
}


def _require_spc(user: User) -> None:
    if user.role != Role.spc:
        raise HTTPException(status_code=403, detail="Only SPC users can manage placement announcements")


async def _ensure_config(session):
    settings = await session.get(PlacementAnnouncementSettings, 1)
    if settings is None:
        settings = PlacementAnnouncementSettings(id=1, templates=DEFAULT_TEMPLATES.copy())
        session.add(settings)
    else:
        existing_template = settings.templates.get("placement_announcement") if settings.templates else None
        settings.templates = {"placement_announcement": existing_template or DEFAULT_TEMPLATES["placement_announcement"]}
    lists = {}
    for key, name in (("all_students", "All Students"),):
        recipient_list = await session.scalar(select(PlacementRecipientList).where(PlacementRecipientList.list_key == key))
        if recipient_list is None:
            recipient_list = PlacementRecipientList(name=name, list_key=key, active=True)
            session.add(recipient_list)
            await session.flush()
        lists[key] = recipient_list
    legacy_lists = (await session.scalars(select(PlacementRecipientList).where(
        PlacementRecipientList.list_key.in_(["mca_considered", "mca_not_considered"]),
    ))).all()
    for legacy_list in legacy_lists:
        all_students = lists["all_students"]
        existing = {item.email for item in (await session.scalars(select(PlacementRecipient).where(
            PlacementRecipient.recipient_list_id == all_students.id,
        ))).all()}
        old_recipients = (await session.scalars(select(PlacementRecipient).where(
            PlacementRecipient.recipient_list_id == legacy_list.id,
            PlacementRecipient.active.is_(True),
        ))).all()
        for item in old_recipients:
            if item.email not in existing:
                session.add(PlacementRecipient(recipient_list_id=all_students.id, email=item.email, name=item.name, active=True))
                existing.add(item.email)
        legacy_list.active = False
    recipients_without_list = (await session.scalars(select(PlacementRecipient).where(
        PlacementRecipient.active.is_(True),
        ~PlacementRecipient.recipient_list_id.in_(select(PlacementRecipientList.id).where(PlacementRecipientList.list_key == "all_students")),
    ))).all()
    existing = {item.email for item in (await session.scalars(select(PlacementRecipient).where(
        PlacementRecipient.recipient_list_id == lists["all_students"].id,
    ))).all()}
    for item in recipients_without_list:
        if item.email not in existing:
            session.add(PlacementRecipient(recipient_list_id=lists["all_students"].id, email=item.email, name=item.name, active=True))
            existing.add(item.email)
    await session.commit()
    await session.refresh(settings)
    return settings, lists


def _valid_google_form(value: str) -> bool:
    parsed = urlparse(value)
    host = (parsed.hostname or "").casefold()
    return parsed.scheme == "https" and (host == "forms.gle" or (host == "docs.google.com" and parsed.path.startswith("/forms/")))


def _settings_response(settings, lists, counts):
    return {
        "placement_director_email": settings.placement_director_email,
        "co_spc_emails": settings.co_spc_emails or [],
        "staff_coordinator_email": settings.staff_coordinator_email,
        "templates": settings.templates or DEFAULT_TEMPLATES,
        "recipient_lists": [
            {"id": recipient_list.id, "name": recipient_list.name, "list_key": recipient_list.list_key,
             "active": recipient_list.active, "active_count": counts.get(recipient_list.id, 0)}
            for recipient_list in lists.values()
        ],
    }


def _campaign_response(campaign):
    return {
        "id": campaign.id,
        "company_id": campaign.company_id,
        "sender_email": campaign.sender_email,
        "template_key": "placement_announcement",
        "subject": campaign.subject,
        "body": campaign.body,
        "additional_details": campaign.additional_details,
        "signature_text": campaign.signature_text,
        "include_signature": campaign.include_signature,
        "to_emails": campaign.to_emails,
        "cc_emails": campaign.cc_emails,
        "bcc_count": campaign.bcc_count,
        "consent_form_url": campaign.consent_form_url,
        "links": campaign.links,
        "attachments": campaign.attachments,
        "attachment_names": campaign.attachment_names,
        "gmail_message_ids": campaign.gmail_message_ids,
        "status": campaign.status,
        "error_details": campaign.error_details,
        "created_at": campaign.created_at,
        "sent_at": campaign.sent_at,
    }


@router.get("/config")
async def get_announcement_config(session: SessionDep, user: CurrentUserDep):
    _require_spc(user)
    settings, lists = await _ensure_config(session)
    counts = {}
    for recipient_list in lists.values():
        counts[recipient_list.id] = await session.scalar(select(func.count(PlacementRecipient.id)).where(
            PlacementRecipient.recipient_list_id == recipient_list.id,
            PlacementRecipient.active.is_(True),
        ))
    return _settings_response(settings, lists, counts)


@router.put("/config")
async def update_announcement_config(payload: AnnouncementSettingsUpdate, session: SessionDep, user: CurrentUserDep):
    _require_spc(user)
    settings, lists = await _ensure_config(session)
    templates = payload.templates
    templates = {"placement_announcement": templates.get("placement_announcement") or DEFAULT_TEMPLATES["placement_announcement"]}
    if not templates["placement_announcement"].get("subject", "").strip() or not templates["placement_announcement"].get("body", "").strip():
        raise HTTPException(status_code=422, detail="The placement announcement needs both a subject and body")
    settings.placement_director_email = str(payload.placement_director_email) if payload.placement_director_email else None
    settings.co_spc_emails = list(dict.fromkeys(str(email).casefold() for email in payload.co_spc_emails))
    settings.staff_coordinator_email = str(payload.staff_coordinator_email) if payload.staff_coordinator_email else None
    settings.templates = templates
    settings.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return await get_announcement_config(session, user)


@router.get("/lists/{list_id}/recipients")
async def get_recipients(list_id: int, session: SessionDep, user: CurrentUserDep):
    _require_spc(user)
    recipient_list = await session.get(PlacementRecipientList, list_id)
    if recipient_list is None:
        raise HTTPException(status_code=404, detail="Recipient list not found")
    recipients = (await session.scalars(select(PlacementRecipient).where(
        PlacementRecipient.recipient_list_id == list_id,
    ).order_by(PlacementRecipient.email))).all()
    return [{"id": item.id, "email": item.email, "name": item.name, "active": item.active} for item in recipients]


@router.post("/lists/{list_id}/import")
async def import_recipients(list_id: int, payload: RecipientImport, session: SessionDep, user: CurrentUserDep):
    _require_spc(user)
    recipient_list = await session.get(PlacementRecipientList, list_id)
    if recipient_list is None:
        raise HTTPException(status_code=404, detail="Recipient list not found")
    parsed: dict[str, str | None] = {}
    for line in payload.content.splitlines():
        for candidate in re.findall(r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}", line, re.IGNORECASE):
            email = candidate.strip(".,;:<>\"'").casefold()
            parsed[email] = None
    if not parsed:
        raise HTTPException(status_code=422, detail="No valid email addresses were found in the import")
    if payload.replace_existing:
        await session.execute(
            PlacementRecipient.__table__.update()
            .where(PlacementRecipient.recipient_list_id == list_id)
            .values(active=False)
        )
    existing = {item.email: item for item in (await session.scalars(select(PlacementRecipient).where(PlacementRecipient.recipient_list_id == list_id))).all()}
    added = 0
    reactivated = 0
    for email in parsed:
        recipient = existing.get(email)
        if recipient:
            if not recipient.active:
                recipient.active = True
                reactivated += 1
        else:
            session.add(PlacementRecipient(recipient_list_id=list_id, email=email, active=True))
            added += 1
    await session.commit()
    return {"added": added, "reactivated": reactivated, "duplicates_removed": len(parsed) - added - reactivated}


@router.patch("/recipients/{recipient_id}")
async def set_recipient_active(recipient_id: int, active: bool, session: SessionDep, user: CurrentUserDep):
    _require_spc(user)
    recipient = await session.get(PlacementRecipient, recipient_id)
    if recipient is None:
        raise HTTPException(status_code=404, detail="Recipient not found")
    recipient.active = active
    await session.commit()
    return {"id": recipient.id, "active": recipient.active}


@router.post("/files", status_code=201)
async def upload_placement_file(file: UploadFile, session: SessionDep, user: CurrentUserDep):
    _require_spc(user)
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.casefold()
    if not filename or suffix not in ALLOWED_FILE_TYPES:
        raise HTTPException(status_code=415, detail="Supported attachments: PDF, DOC, DOCX and XLSX")
    if file.content_type not in ALLOWED_FILE_TYPES[suffix]:
        raise HTTPException(status_code=415, detail="File type does not match a supported attachment")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Attachment must be between 1 byte and 8 MB")
    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="The file is not a valid PDF")
    if suffix in {".docx", ".xlsx"} and not content.startswith(b"PK"):
        raise HTTPException(status_code=415, detail="The file is not a valid Office document")
    attachment = PlacementAttachment(uploaded_by=user.id, filename=filename[:255], content_type=file.content_type, content=content)
    session.add(attachment)
    await session.commit()
    return {"id": attachment.id, "filename": attachment.filename, "content_type": attachment.content_type, "size": len(content)}


@router.get("/files")
async def list_placement_files(session: SessionDep, user: CurrentUserDep):
    _require_spc(user)
    files = (await session.scalars(select(PlacementAttachment).where(PlacementAttachment.uploaded_by == user.id).order_by(PlacementAttachment.created_at.desc()))).all()
    return [{"id": item.id, "filename": item.filename, "content_type": item.content_type, "size": len(item.content)} for item in files]


@router.get("/files/{file_id}")
async def get_placement_file(file_id: int, session: SessionDep, user: CurrentUserDep):
    _require_spc(user)
    attachment = await session.get(PlacementAttachment, file_id)
    if attachment is None or attachment.uploaded_by != user.id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    filename = attachment.filename.replace('"', "")
    return Response(content=attachment.content, media_type=attachment.content_type, headers={"Content-Disposition": f'inline; filename="{filename}"'})


@router.get("/companies/{company_id}/source-attachments")
async def get_source_attachments(company_id: int, session: SessionDep, user: CurrentUserDep):
    _require_spc(user)
    opportunity = await session.scalar(select(PendingPlacementOpportunity).where(
        PendingPlacementOpportunity.published_company_id == company_id,
        PendingPlacementOpportunity.review_status == "APPROVED",
    ))
    if opportunity is None or opportunity.source_email_id is None:
        return []
    email = await session.get(ProcessedEmail, opportunity.source_email_id)
    attachments = (email.extracted_data or {}).get("attachments", []) if email else []
    integration = await session.scalar(select(GmailIntegration).where(GmailIntegration.connected.is_(True)))
    if integration is None:
        return []
    access_token = await get_access_token(integration)
    import httpx
    results = []
    async with httpx.AsyncClient(timeout=15) as client:
        for item in attachments:
            response = await client.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{email.gmail_message_id}/attachments/{item['attachment_id']}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if not response.is_error:
                results.append({**item, "source_email_id": email.id, "gmail_message_id": email.gmail_message_id})
    return results


async def _validate_campaign_attachments(session, user, company_id, attachments):
    uploaded = []
    source_items = []
    for item in attachments:
        if item.kind == "upload":
            if not item.file_id:
                raise HTTPException(status_code=422, detail="Uploaded attachment is missing its file ID")
            file = await session.get(PlacementAttachment, item.file_id)
            if file is None or file.uploaded_by != user.id:
                raise HTTPException(status_code=404, detail="Selected uploaded attachment was not found")
            uploaded.append(file)
        else:
            if not item.source_email_id or not item.gmail_message_id or not item.attachment_id:
                raise HTTPException(status_code=422, detail="Inbox attachment is missing its source reference")
            opportunity = await session.scalar(select(PendingPlacementOpportunity).where(
                PendingPlacementOpportunity.published_company_id == company_id,
                PendingPlacementOpportunity.source_email_id == item.source_email_id,
                PendingPlacementOpportunity.review_status == "APPROVED",
            ))
            source_email = await session.get(ProcessedEmail, item.source_email_id)
            refs = (source_email.extracted_data or {}).get("attachments", []) if source_email else []
            match = next((ref for ref in refs if ref.get("attachment_id") == item.attachment_id and ref.get("filename") == item.filename), None)
            if opportunity is None or source_email is None or source_email.gmail_message_id != item.gmail_message_id or match is None:
                raise HTTPException(status_code=422, detail="Selected inbox attachment is not attached to this approved opportunity")
            source_items.append((item, match))
    return uploaded, source_items


@router.post("/campaigns", status_code=201)
async def create_campaign_draft(payload: CampaignDraftInput, session: SessionDep, user: CurrentUserDep):
    _require_spc(user)
    existing_campaign = await session.scalar(select(PlacementCampaign).where(PlacementCampaign.request_key == payload.request_key))
    if existing_campaign:
        if existing_campaign.initiated_by != user.id:
            raise HTTPException(status_code=409, detail="This campaign key is already in use")
        return _campaign_response(existing_campaign)
    opportunity = await session.scalar(select(PendingPlacementOpportunity).where(
        PendingPlacementOpportunity.published_company_id == payload.company_id,
        PendingPlacementOpportunity.review_status == "APPROVED",
    ))
    company = await session.get(Company, payload.company_id)
    recipient_list = await session.get(PlacementRecipientList, payload.recipient_list_id)
    sender_account = await session.scalar(select(GmailSendingAccount).where(
        GmailSendingAccount.user_id == user.id,
        GmailSendingAccount.connected.is_(True),
    ))
    if company is None:
        raise HTTPException(status_code=404, detail="Published opportunity not found")
    if opportunity is None:
        raise HTTPException(status_code=422, detail="Announcements can only be sent for a published opportunity approved by an SPC")
    if recipient_list is None or not recipient_list.active:
        raise HTTPException(status_code=422, detail="Choose an active student distribution list")
    if sender_account is None:
        raise HTTPException(status_code=409, detail="Connect your own Gmail sending account before creating a campaign")
    consent_url = str(payload.consent_form_url)
    if not _valid_google_form(consent_url):
        raise HTTPException(status_code=422, detail="Consent link must be a Google Forms URL")
    settings, _ = await _ensure_config(session)
    default_to = [settings.placement_director_email] if settings.placement_director_email else []
    default_cc = [*(settings.co_spc_emails or []), *([settings.staff_coordinator_email] if settings.staff_coordinator_email else [])]
    to_emails = list(dict.fromkeys(str(email).casefold() for email in (payload.to_emails if payload.to_emails is not None else default_to)))
    cc_emails = list(dict.fromkeys(str(email).casefold() for email in (payload.cc_emails if payload.cc_emails is not None else default_cc)))
    if not to_emails:
        raise HTTPException(status_code=422, detail="Set the Placement Director email in announcement settings")
    bcc_count = await session.scalar(select(func.count(PlacementRecipient.id)).where(
        PlacementRecipient.recipient_list_id == recipient_list.id,
        PlacementRecipient.active.is_(True),
    ))
    if not bcc_count:
        raise HTTPException(status_code=422, detail="The selected distribution list has no active recipients")
    list_recipients = (await session.scalars(select(PlacementRecipient.email).where(
        PlacementRecipient.recipient_list_id == recipient_list.id,
        PlacementRecipient.active.is_(True),
    ))).all()
    bcc_set = {email.casefold() for email in list_recipients}
    if bcc_set.intersection(email.casefold() for email in [*to_emails, *cc_emails]):
        raise HTTPException(status_code=422, detail="An email cannot be both a visible recipient and a student BCC recipient")
    uploaded, source_items = await _validate_campaign_attachments(session, user, company.id, payload.attachments)
    attachment_names = [file.filename for file in uploaded] + [item.filename for item, _ in source_items]
    campaign_body = payload.body.strip()
    campaign = PlacementCampaign(
        company_id=company.id,
        recipient_list_id=recipient_list.id,
        initiated_by=user.id,
        sender_email=sender_account.email_address,
        template_key="placement_announcement",
        subject=payload.subject.strip(),
        body=campaign_body,
        additional_details=payload.additional_details,
        signature_text=sender_account.signature_text,
        include_signature=payload.include_signature,
        to_emails=to_emails,
        cc_emails=cc_emails,
        bcc_count=bcc_count,
        consent_form_url=consent_url,
        links=[{"label": item.label, "url": str(item.url)} for item in payload.links],
        attachments=[item.model_dump(mode="json") for item in payload.attachments],
        attachment_names=attachment_names,
        request_key=payload.request_key,
        status="DRAFT",
    )
    session.add(campaign)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing_campaign = await session.scalar(select(PlacementCampaign).where(PlacementCampaign.request_key == payload.request_key))
        if existing_campaign and existing_campaign.initiated_by == user.id:
            return _campaign_response(existing_campaign)
        raise HTTPException(status_code=409, detail="Campaign could not be saved due to a duplicate request")
    await session.refresh(campaign)
    return _campaign_response(campaign)


async def _materialize_attachments(session, user, campaign):
    from app.schema.models import CampaignAttachmentInput
    attachments = [CampaignAttachmentInput.model_validate(item) for item in campaign.attachments]
    uploaded, source_items = await _validate_campaign_attachments(session, user, campaign.company_id, attachments)
    files = [(item.filename, item.content_type, item.content) for item in uploaded]
    if source_items:
        integration = await session.scalar(select(GmailIntegration).where(GmailIntegration.connected.is_(True)))
        if integration is None:
            raise HTTPException(status_code=409, detail="The primary inbox connection is needed to retrieve selected email attachments")
        inbox_token = await get_access_token(integration)
        for item, ref in source_items:
            content = await fetch_message_attachment(inbox_token, item.gmail_message_id, item.attachment_id)
            files.append((item.filename, str(ref.get("mime_type") or "application/octet-stream"), content))
    total = sum(len(content) for _, _, content in files)
    if total > MAX_MESSAGE_BYTES:
        raise HTTPException(status_code=413, detail="Selected attachments exceed the 20 MB email limit")
    return files


@router.get("/campaigns")
async def list_campaigns(session: SessionDep, user: CurrentUserDep):
    _require_spc(user)
    campaigns = (await session.scalars(select(PlacementCampaign).where(
        PlacementCampaign.initiated_by == user.id,
    ).order_by(PlacementCampaign.created_at.desc()).limit(100))).all()
    return [_campaign_response(campaign) for campaign in campaigns]


@router.post("/campaigns/{campaign_id}/send")
async def send_campaign(campaign_id: int, payload: CampaignSendRequest, session: SessionDep, user: CurrentUserDep):
    _require_spc(user)
    campaign = await session.get(PlacementCampaign, campaign_id)
    if campaign is None or campaign.initiated_by != user.id:
        raise HTTPException(status_code=404, detail="Campaign draft not found")
    if campaign.request_key != payload.request_key:
        raise HTTPException(status_code=409, detail="Campaign request key does not match the saved draft")
    if campaign.status in {"SENT", "PARTIALLY_SENT", "SENDING"}:
        raise HTTPException(status_code=409, detail=f"Campaign is already {campaign.status.lower()}")
    if campaign.status == "FAILED" and campaign.gmail_message_ids:
        raise HTTPException(status_code=409, detail="This campaign partially sent and cannot be retried safely. Create a new draft for remaining recipients.")
    campaign = await session.scalar(select(PlacementCampaign).where(PlacementCampaign.id == campaign_id).with_for_update())
    if campaign is None or campaign.status in {"SENT", "PARTIALLY_SENT", "SENDING"}:
        raise HTTPException(status_code=409, detail="This campaign is already being sent or has finished")
    company = await session.get(Company, campaign.company_id)
    sender_account = await session.scalar(select(GmailSendingAccount).where(
        GmailSendingAccount.user_id == user.id,
        GmailSendingAccount.connected.is_(True),
    ))
    if company is None or sender_account is None or sender_account.email_address.casefold() != campaign.sender_email.casefold():
        raise HTTPException(status_code=409, detail="Your connected sending Gmail account changed. Reconnect or create a new draft.")
    recipients = (await session.scalars(select(PlacementRecipient).where(
        PlacementRecipient.recipient_list_id == campaign.recipient_list_id,
        PlacementRecipient.active.is_(True),
    ).order_by(PlacementRecipient.id))).all()
    visible_recipients = {email.casefold() for email in [*campaign.to_emails, *campaign.cc_emails]}
    bcc_emails = [item.email for item in recipients if item.email.casefold() not in visible_recipients]
    if not bcc_emails:
        raise HTTPException(status_code=422, detail="The selected distribution list has no active BCC recipients")
    if len(campaign.to_emails) + len(campaign.cc_emails) >= 450:
        raise HTTPException(status_code=422, detail="TO and CC recipients exceed the safe per-message Gmail limit")
    try:
        attachments = await _materialize_attachments(session, user, campaign)
        if sum(len(content) for _, _, content in attachments) > MAX_MESSAGE_BYTES:
            raise HTTPException(status_code=413, detail="Selected attachments exceed the 20 MB email limit")
        token = await get_sender_access_token(session, user, sender_account)
    except HTTPException:
        raise
    except Exception as exc:
        campaign.status = "FAILED"
        campaign.error_details = str(exc)[:2000]
        campaign.updated_at = datetime.now(timezone.utc)
        await session.commit()
        raise HTTPException(status_code=502, detail="Unable to prepare this campaign for sending. Recheck the Gmail connection and selected attachments.") from exc

    campaign.status = "SENDING"
    campaign.bcc_count = len(bcc_emails)
    campaign.updated_at = datetime.now(timezone.utc)
    await session.commit()
    per_batch = 450 - len(campaign.to_emails) - len(campaign.cc_emails)
    batches = [bcc_emails[index:index + per_batch] for index in range(0, len(bcc_emails), per_batch)]
    message_ids: list[str] = []
    errors: list[str] = []
    for batch in batches:
        try:
            raw = build_announcement_message(
                sender=campaign.sender_email,
                to_emails=campaign.to_emails,
                cc_emails=campaign.cc_emails,
                bcc_emails=batch,
                subject=campaign.subject,
                body=campaign.body,
                signature_text=campaign.signature_text,
                include_signature=campaign.include_signature,
                consent_form_url=campaign.consent_form_url,
                links=campaign.links,
                additional_details=campaign.additional_details or {},
                attachments=attachments,
            )
            message_ids.append(await send_gmail_message(token, raw))
        except Exception as exc:
            errors.append(str(exc)[:1000])
            break
    campaign.gmail_message_ids = message_ids
    campaign.error_details = "\n".join(errors) if errors else None
    campaign.status = "SENT" if not errors else "PARTIALLY_SENT" if message_ids else "FAILED"
    campaign.sent_at = datetime.now(timezone.utc) if message_ids else None
    campaign.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(campaign)
    return _campaign_response(campaign)
