import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.service.email_sender import send_template_email

logger = logging.getLogger(__name__)
EVENT_TIMEZONE = ZoneInfo("Asia/Kolkata")


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
    from app.tasks.mail_tasks import send_interest_notification
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

    # datetime-local values have no timezone. Interpret them in the app's
    # user-facing timezone, then convert to UTC for Celery's ETA.
    if company_date.tzinfo is None:
        company_date = company_date.replace(tzinfo=EVENT_TIMEZONE)
    event_time = company_date.astimezone(timezone.utc)
    reminder_time = event_time - timedelta(hours=1)
    now = datetime.now(timezone.utc)
    if event_time <= now:
        logger.info("Skipping reminder for past event company_id=%s event_time=%s", company_id, event_time)
        return
    try:
        # If the event is less than an hour away, send the reminder now.
        eta = max(reminder_time, now)
        result = send_event_reminder.apply_async(args=[company_id], eta=eta)
        logger.info(
            "Queued event reminder company_id=%s event_time=%s eta=%s task_id=%s",
            company_id,
            event_time.isoformat(),
            eta.isoformat(),
            result.id,
        )
    except Exception:
        logger.exception("Unable to queue event reminder")
