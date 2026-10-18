## Mail notifications

Mail credentials and Celery connection settings are read from environment variables. Add the values listed in `.env.example` to your local `.env`; the application does not provide defaults for real SMTP credentials.

Start Redis, then run the API and a Celery worker from this directory:

```bash
celery -A app.tasks.mail_tasks:celery_app worker --loglevel=INFO
```

The API queues an email when a user saves an opportunity. A company reminder is queued for one hour before its event date and is sent only to users who saved that company. Emails are rendered with the Jinja templates in `app/templates/email/` and delivered through `fastapi-mail`.

The authenticated saved-role endpoint is `GET /company/saved`. The existing `PATCH /company/interested/{company_id}` endpoint toggles a saved role and queues the confirmation notification when the role becomes saved.

## Hosting on Render

The repository's `render.yaml` defines the API, static frontend, Celery worker, Redis-compatible queue, and PostgreSQL database. Create a Blueprint from the repository in Render. The first deploy uses a fresh database; `scripts/bootstrap_db.py` creates the current schema and stamps it as the Alembic baseline, then applies future migrations normally.

Set the prompted values without committing them: `GOOGLE_CLIENT_ID`, `RVCE_EMAIL_DOMAIN`, `SPC_EMAILS`, `CORS_ORIGINS`, `VITE_GOOGLE_CLIENT_ID`, and the SMTP values for the worker. `CORS_ORIGINS` is the exact HTTPS origin of the static site, such as `https://driveboard-rvce.onrender.com`; the Google client must also allow that origin. Use the same Google Client ID for backend and frontend.

The Blueprint uses free API, PostgreSQL, and queue plans for an initial preview; Render's free Postgres expires after 30 days and free Key Value data is not persistent. The Celery worker uses a paid starter plan because Render does not offer free background workers. Upgrade the database and queue before relying on persistent production data or queued notifications.
