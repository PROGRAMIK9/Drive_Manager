import asyncio
import logging
from datetime import datetime

from celery import Celery
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config.config import celery_settings
from app.database.database import engine
from app.schema.database import Company, Interested, Role, User
from app.service.email_sender import send_template_email

logger = logging.getLogger(__name__)

celery_app = Celery(
    "driveboard",
    broker=celery_settings.CELERY_BROKER_URL,
    backend=celery_settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    enable_utc=True,
    timezone="UTC",
)


@celery_app.task(name="mail.send_interest_notification")
def send_interest_notification(
    recipient: str,
    recipient_name: str,
    company_name: str,
    company_location: str,
    company_date: str,
) -> None:
    asyncio.run(send_template_email(
        recipient=recipient,
        subject=f"Saved: {company_name}",
        template_name="interest_saved.html",
        context={
            "recipient_name": recipient_name,
            "company_name": company_name,
            "company_location": company_location,
            "company_date": datetime.fromisoformat(company_date),
        },
    ))


@celery_app.task(name="mail.send_verification_email")
def send_verification_email(recipient: str, recipient_name: str, verification_url: str) -> None:
    asyncio.run(send_template_email(
        recipient=recipient,
        subject="Verify your Driveboard account",
        template_name="verify_account.html",
        context={"recipient_name": recipient_name, "verification_url": verification_url},
    ))


@celery_app.task(name="mail.send_event_reminder")
def send_event_reminder(company_id: int) -> None:
    logger.info("Running event reminder for company %s", company_id)
    asyncio.run(_send_event_reminder(company_id))


async def _send_event_reminder(company_id: int) -> None:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        company = await session.get(Company, company_id)
        if not company:
            logger.warning("Skipping event reminder: company %s was not found", company_id)
            return

        users = (
            await session.scalars(
                select(User)
                .outerjoin(Interested, Interested.user_id == User.id)
                .where(
                    or_(
                        User.role == Role.spc,
                        (Interested.company_id == company_id)
                        & Interested.interested.is_(True),
                    )
                )
                .distinct()
            )
        ).all()
        logger.info(
            "Sending event reminder for company %s to %s recipients",
            company_id,
            len(users),
        )
        for user in users:
            await send_template_email(
                recipient=user.email,
                subject=f"Event starting: {company.name}",
                template_name="event_reminder.html",
                context={
                    "recipient_name": user.name,
                    "company_name": company.name,
                    "company_location": company.location,
                    "company_date": company.date,
                },
            )
        logger.info("Finished event reminder for company %s", company_id)
