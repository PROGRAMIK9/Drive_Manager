import logging
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.database.database import engine
from app.schema.database import Company, EventReminder, Interested, Role, User
from app.service.email_sender import send_template_email

logger = logging.getLogger(__name__)

async def send_interest_notification(
    recipient: str,
    recipient_name: str,
    company_name: str,
    company_location: str,
    company_date: str,
) -> None:
    await send_template_email(
        recipient=recipient,
        subject=f"Saved: {company_name}",
        template_name="interest_saved.html",
        context={
            "recipient_name": recipient_name,
            "company_name": company_name,
            "company_location": company_location,
            "company_date": datetime.fromisoformat(company_date),
        },
    )


async def send_verification_email(recipient: str, recipient_name: str, verification_url: str) -> None:
    await send_template_email(
        recipient=recipient,
        subject="Verify your Driveboard account",
        template_name="verify_account.html",
        context={"recipient_name": recipient_name, "verification_url": verification_url},
    )


async def send_due_event_reminder(company_id: int) -> None:
    logger.info("Running event reminder for company %s", company_id)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        reminder = await session.scalar(
            select(EventReminder).where(EventReminder.company_id == company_id)
        )
        company = await session.get(Company, company_id)
        if not reminder or not company or reminder.sent_at is not None:
            return

        try:
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
            logger.info("Sending event reminder for company %s to %s recipients", company_id, len(users))
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
            reminder.sent_at = datetime.now().astimezone()
            reminder.claimed_at = None
            await session.commit()
            logger.info("Finished event reminder for company %s", company_id)
        except Exception:
            logger.exception("Event reminder failed for company %s; it will be retried", company_id)
            reminder.claimed_at = None
            await session.commit()
