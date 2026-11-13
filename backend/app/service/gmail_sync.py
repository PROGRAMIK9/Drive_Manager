from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import base64
import hashlib
import re

import httpx
from fastapi import HTTPException

from app.config.config import gmail_settings
from app.schema.database import GmailIntegration
from app.schema.database import ProcessedEmail
from app.service.gmail_security import GmailCredentialError, decrypt_refresh_token, encrypt_refresh_token
from app.service.email_sender_policy import is_accepted_placement_sender
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

TOKEN_URL = "https://oauth2.googleapis.com/token"


async def get_access_token(integration: GmailIntegration) -> str:
    if not integration.encrypted_refresh_token:
        raise GmailCredentialError("Gmail mailbox has no stored refresh token")
    refresh_token = decrypt_refresh_token(integration.encrypted_refresh_token)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(TOKEN_URL, data={
            "client_id": gmail_settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": gmail_settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
    if response.is_error:
        raise HTTPException(status_code=401, detail="Gmail authorization expired or was revoked; reconnect it")
    tokens = response.json()
    if tokens.get("refresh_token"):
        integration.encrypted_refresh_token = encrypt_refresh_token(tokens["refresh_token"])
    return tokens["access_token"]


async def start_gmail_watch(integration: GmailIntegration, access_token: str) -> dict:
    topic = gmail_settings.GOOGLE_PUBSUB_TOPIC.strip()
    if not topic:
        raise HTTPException(status_code=503, detail="Google Pub/Sub topic is not configured")
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/watch",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"topicName": topic, "labelIds": ["INBOX"], "labelFilterBehavior": "INCLUDE"},
        )
    if response.is_error:
        raise HTTPException(status_code=502, detail="Gmail Watch setup failed; check topic permissions and Gmail authorization")
    result = response.json()
    integration.last_history_id = str(result.get("historyId", "")) or None
    expiration = result.get("expiration")
    integration.watch_expiration = datetime.fromtimestamp(int(expiration) / 1000, timezone.utc) if expiration else None
    integration.last_sync_at = datetime.now(timezone.utc)
    integration.last_error = None
    integration.updated_at = datetime.now(timezone.utc)
    return result


async def list_history(access_token: str, start_history_id: str) -> tuple[list[str], str]:
    ids: set[str] = set()
    page_token: str | None = None
    history_id = start_history_id
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params: dict[str, str | int] = {"startHistoryId": start_history_id, "historyTypes": "messageAdded", "maxResults": 500}
            if page_token:
                params["pageToken"] = page_token
            response = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/history",
                headers={"Authorization": f"Bearer {access_token}"}, params=params,
            )
            if response.status_code == 404:
                raise HTTPException(status_code=409, detail="Gmail history expired; a full mailbox sync is required")
            if response.is_error:
                raise HTTPException(status_code=502, detail="Could not retrieve Gmail history")
            result = response.json()
            history_id = str(result.get("historyId") or history_id)
            for record in result.get("history", []):
                for entry in record.get("messagesAdded", []):
                    message = entry.get("message", {})
                    if message.get("id"):
                        ids.add(str(message["id"]))
            page_token = result.get("nextPageToken")
            if not page_token:
                break
    return sorted(ids), history_id


async def list_messages_since(access_token: str, since: datetime) -> list[str]:
    """Recover from an expired Gmail history cursor using a narrow inbox search."""
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    epoch_seconds = int(since.timestamp())
    ids: set[str] = set()
    page_token: str | None = None
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params: dict[str, str | int] = {
                "q": f"after:{epoch_seconds}",
                "maxResults": 500,
            }
            if page_token:
                params["pageToken"] = page_token
            response = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            if response.is_error:
                raise HTTPException(status_code=502, detail="Could not recover Gmail messages after history expiration")
            result = response.json()
            for message in result.get("messages", []):
                if message.get("id"):
                    ids.add(str(message["id"]))
            page_token = result.get("nextPageToken")
            if not page_token:
                break
    return sorted(ids)


def _decode_part(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")
    except Exception:
        return ""


def parse_gmail_message(message: dict) -> dict:
    headers = {str(h.get("name", "")).casefold(): str(h.get("value", "")) for h in message.get("payload", {}).get("headers", [])}
    parts: list[tuple[str, str]] = []
    attachments: list[dict[str, str | int]] = []
    def visit(part: dict) -> None:
        mime = str(part.get("mimeType", "")).casefold()
        body = part.get("body", {})
        filename = str(part.get("filename", "")).strip()
        attachment_id = body.get("attachmentId")
        if filename and attachment_id:
            attachments.append({"filename": filename[:255], "mime_type": mime[:120] or "application/octet-stream", "attachment_id": str(attachment_id), "size": int(body.get("size") or 0)})
        if body.get("data") and mime in {"text/plain", "text/html"}:
            parts.append((mime, _decode_part(body["data"])))
        for child in part.get("parts", []):
            visit(child)
    visit(message.get("payload", {}))
    plain = next((body for mime, body in parts if mime == "text/plain"), "")
    html_text = next((re.sub(r"<[^>]+>", " ", body) for mime, body in parts if mime == "text/html"), "")
    body = plain or html_text
    body = re.split(r"\nOn .{5,160}wrote:\s*$|\n-{2,}\s*Original Message\s*-{2,}", body, maxsplit=1, flags=re.IGNORECASE | re.MULTILINE)[0]
    sender = headers.get("from", "")
    received = None
    if headers.get("date"):
        try:
            received = parsedate_to_datetime(headers["date"])
        except (TypeError, ValueError, OverflowError):
            pass
    digest = hashlib.sha256((headers.get("subject", "") + "\n" + body).encode("utf-8")).hexdigest()
    return {
        "gmail_message_id": str(message.get("id", "")),
        "gmail_thread_id": message.get("threadId"),
        "sender": sender,
        "subject": headers.get("subject", ""),
        "received_at": received,
        "body": body,
        "attachments": attachments,
        "content_hash": digest,
        "accepted_sender": is_accepted_placement_sender(sender),
        "source_link": f"https://mail.google.com/mail/u/0/#all/{message.get('id', '')}",
    }


async def fetch_message(access_token: str, message_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
            headers={"Authorization": f"Bearer {access_token}"}, params={"format": "full"},
        )
    if response.is_error:
        raise HTTPException(status_code=502, detail="Could not retrieve a Gmail message")
    return parse_gmail_message(response.json())


async def fetch_message_attachment(access_token: str, message_id: str, attachment_id: str) -> bytes:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/attachments/{attachment_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.is_error:
        raise HTTPException(status_code=502, detail="Could not retrieve the selected inbox attachment")
    try:
        data = str(response.json().get("data", ""))
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Gmail returned an invalid attachment") from exc


async def store_fetched_message(session: AsyncSession, message_data: dict) -> ProcessedEmail:
    existing = await session.scalar(select(ProcessedEmail).where(ProcessedEmail.gmail_message_id == message_data["gmail_message_id"]))
    if existing:
        return existing
    accepted = message_data["accepted_sender"]
    record = ProcessedEmail(
        gmail_message_id=message_data["gmail_message_id"],
        gmail_thread_id=message_data.get("gmail_thread_id"),
        sender=message_data.get("sender"),
        subject=message_data.get("subject"),
        received_at=message_data.get("received_at"),
        classification="UNCERTAIN",
        processing_status="RECEIVED" if accepted else "IGNORED_SENDER",
        processing_error=None,
        extracted_data={"body": message_data.get("body", ""), "attachments": message_data.get("attachments", [])} if accepted else {},
        source_link=message_data.get("source_link"),
        content_hash=message_data.get("content_hash"),
    )
    session.add(record)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        existing = await session.scalar(select(ProcessedEmail).where(ProcessedEmail.gmail_message_id == message_data["gmail_message_id"]))
        if existing:
            return existing
        raise
    await session.refresh(record)
    return record
