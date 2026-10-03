import logging
from datetime import datetime, timedelta
from pathlib import Path

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from app.config.config import mail_settings
logger = logging.getLogger(__name__)
TEMPLATE_FOLDER = Path(__file__).parent.parent / "templates" / "email"


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


def queue_verification_email(*, recipient: str, recipient_name: str, verification_url: str) -> None:
    try:
        from app.tasks.mail_tasks import send_verification_email
        send_verification_email.delay(recipient, recipient_name, verification_url)
    except Exception:
        logger.exception("Unable to queue verification email")


def queue_interest_notification(
    *,
    recipient: str,
    recipient_name: str,
    company_name: str,
    company_location: str,
    company_date: datetime,
) -> None:
    try:
        send_interest_notification.delay(
            recipient,
            recipient_name,
            company_name,
            company_location,
            company_date.isoformat(),
        )
    except Exception:
        logger.exception("Unable to queue interest notification")


def queue_event_reminder(company_id: int, company_date: datetime) -> None:
    from app.tasks.mail_tasks import send_event_reminder

    reminder_at = company_date - timedelta(hours=1)
    if reminder_at <= datetime.now():
        return
    try:
        send_event_reminder.apply_async(args=[company_id], eta=reminder_at)
    except Exception:
        logger.exception("Unable to queue event reminder")