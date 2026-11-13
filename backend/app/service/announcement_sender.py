"""Send SPC announcements through the authenticated SPC's own Gmail account."""
import base64
import html
import mimetypes
import re
from email.message import EmailMessage
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
    message.set_content(signed_body)

    escaped_body = html.escape(signed_body)
    safe_body = re.sub(
        r"https?://[^\s<]+",
        lambda match: f'<a href="{match.group(0)}">{match.group(0)}</a>',
        escaped_body,
    ).replace("\n", "<br>")
    html_content = (
        f"<div style=\"font-family:Arial,sans-serif;line-height:1.6\"><p>{safe_body}</p>"
        "</div>"
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
