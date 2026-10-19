import asyncio
import json
from pathlib import Path

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from jinja2 import Environment, FileSystemLoader, select_autoescape
import urllib3

from app.config.config import mail_settings

TEMPLATE_FOLDER = Path(__file__).parent.parent / "templates" / "email"
template_environment = Environment(
    loader=FileSystemLoader(TEMPLATE_FOLDER),
    autoescape=select_autoescape(["html"]),
)


def get_mail_config() -> ConnectionConfig:
    return ConnectionConfig(
        MAIL_USERNAME=mail_settings.MAIL_USERNAME,
        MAIL_PASSWORD=mail_settings.MAIL_PASSWORD,
        MAIL_PORT=mail_settings.MAIL_PORT,
        MAIL_SERVER=mail_settings.MAIL_SERVER,
        MAIL_STARTTLS=mail_settings.MAIL_STARTTLS,
        MAIL_SSL_TLS=mail_settings.MAIL_SSL_TLS,
        MAIL_FROM=mail_settings.MAIL_FROM,
        MAIL_FROM_NAME=mail_settings.MAIL_FROM_NAME,
        TEMPLATE_FOLDER=TEMPLATE_FOLDER,
    )


async def send_template_email(
    *,
    recipient: str,
    subject: str,
    template_name: str,
    context: dict,
) -> None:
    if mail_settings.BREVO_API_KEY:
        template = template_environment.get_template(template_name)
        html = template.render(**context)
        payload = json.dumps({
            "sender": {
                "name": mail_settings.MAIL_FROM_NAME,
                "email": mail_settings.MAIL_FROM,
            },
            "to": [{"email": recipient}],
            "subject": subject,
            "htmlContent": html,
        }).encode("utf-8")
        response = await asyncio.to_thread(
            urllib3.request,
            "POST",
            "https://api.brevo.com/v3/smtp/email",
            body=payload,
            headers={
                "api-key": mail_settings.BREVO_API_KEY,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=urllib3.Timeout(connect=5.0, read=20.0),
        )
        if response.status >= 300:
            raise RuntimeError(
                f"Brevo email request failed ({response.status}): "
                f"{response.data.decode('utf-8', errors='replace')}"
            )
        return

    message = MessageSchema(
        recipients=[recipient],
        subject=subject,
        subtype=MessageType.html,
        template_body=context,
    )
    await FastMail(get_mail_config()).send_message(
        message,
        template_name=template_name,
    )
