"""Send SPC announcements through the authenticated SPC's own Gmail account."""
import base64
import html
import mimetypes
from email.message import EmailMessage
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.config import gmail_settings
from app.schema.database import GmailSendingAccount, User
from app.service.gmail_security import decrypt_refresh_token, encrypt_refresh_token

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


async def get_sender_access_token(session: AsyncSession, user: User, account: GmailSendingAccount) -> str:
    refresh_token = decrypt_refresh_token(account.encrypted_refresh_token)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(GOOGLE_TOKEN_URL, data={
            "client_id": gmail_settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": gmail_settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
    if response.is_error:
        raise RuntimeError("The connected sending Gmail authorization expired or was revoked. Reconnect it.")
    tokens = response.json()
    access_token = tokens.get("access_token")
    if not access_token:
        raise RuntimeError("Google did not return a Gmail sending access token")
    if tokens.get("refresh_token"):
        account.encrypted_refresh_token = encrypt_refresh_token(tokens["refresh_token"])
        await session.commit()
        await session.refresh(account)
    return access_token


def build_announcement_message(
    *,
    sender: str,
    to_emails: list[str],
    cc_emails: list[str],
    bcc_emails: list[str],
    subject: str,
    body: str,
    signature_text: str,
    include_signature: bool,
    consent_form_url: str,
    links: list[dict[str, str]],
    additional_details: dict[str, Any],
    attachments: list[tuple[str, str, bytes]],
) -> str:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(to_emails)
    if cc_emails:
        message["Cc"] = ", ".join(cc_emails)
    if bcc_emails:
        message["Bcc"] = ", ".join(bcc_emails)
    message["Subject"] = subject
    signed_body = f"{body.rstrip()}\n\n{signature_text.strip()}" if include_signature and signature_text.strip() else body
    def display(value: Any) -> str:
        if isinstance(value, list):
            return ", ".join(display(item) for item in value)
        if isinstance(value, dict):
            return "; ".join(f"{key}: {display(item)}" for key, item in value.items())
        return str(value)

    details_lines = [f"{key.replace('_', ' ').title()}: {display(value)}" for key, value in additional_details.items() if value not in (None, "", [], {}) and key != "original_email_body"]
    details_text = "\n".join(details_lines)
    plain_body = f"{signed_body}\n\n{details_text}\n\nConsent form: {consent_form_url}" if details_text else f"{signed_body}\n\nConsent form: {consent_form_url}"
    message.set_content(plain_body + "".join(f"\n{link['label']}: {link['url']}" for link in links))

    safe_body = "<br>".join(html.escape(line) for line in signed_body.splitlines())
    links_html = "".join(
        f'<li><a href="{html.escape(link["url"], quote=True)}">{html.escape(link["label"])}</a></li>'
        for link in links
    )
    details_html = "".join(f"<p><strong>{html.escape(key.replace('_', ' ').title())}:</strong> {html.escape(display(value))}</p>" for key, value in additional_details.items() if value not in (None, "", [], {}) and key != "original_email_body")
    html_content = (
        f"<div style=\"font-family:Arial,sans-serif;line-height:1.6\"><p>{safe_body}</p>"
        f"{details_html}"
        f'<p><a href="{html.escape(consent_form_url, quote=True)}">Submit the required consent form</a></p>'
        f"{f'<ul>{links_html}</ul>' if links_html else ''}</div>"
    )
    message.add_alternative(html_content, subtype="html")
    for filename, content_type, data in attachments:
        guessed_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        maintype, _, subtype = guessed_type.partition("/")
        if not subtype:
            maintype, subtype = "application", "octet-stream"
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")


async def send_gmail_message(access_token: str, raw_message: str) -> str:
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            GMAIL_SEND_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            json={"raw": raw_message},
        )
    if response.is_error:
        try:
            detail = response.json().get("error", {}).get("message", "Gmail rejected the message")
        except (ValueError, AttributeError):
            detail = "Gmail rejected the message"
        raise RuntimeError(f"Gmail send failed ({response.status_code}): {str(detail)[:500]}")
    result = response.json()
    message_id = result.get("id")
    if not message_id:
        raise RuntimeError("Gmail accepted the request without returning a message ID")
    return str(message_id)
