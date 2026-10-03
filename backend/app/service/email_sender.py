from pathlib import Path

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from app.config.config import mail_settings

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
