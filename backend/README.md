## Mail notifications

Mail credentials and Celery connection settings are read from environment variables. Add the values listed in `.env.example` to your local `.env`; the application does not provide defaults for real SMTP credentials.

Start Redis, then run the API and a Celery worker from this directory:

```bash
celery -A app.tasks.mail_tasks:celery_app worker --loglevel=INFO
```

The API queues an email when a user saves an opportunity. A company reminder is queued for one hour before its event date and is sent only to users who saved that company. Emails are rendered with the Jinja templates in `app/templates/email/` and delivered through `fastapi-mail`.

The authenticated saved-role endpoint is `GET /company/saved`. The existing `PATCH /company/interested/{company_id}` endpoint toggles a saved role and queues the confirmation notification when the role becomes saved.
