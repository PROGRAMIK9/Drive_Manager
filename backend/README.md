## Mail notifications

Mail credentials are read from environment variables. Add the values listed in `.env.example` to your local `.env`; the application does not provide defaults for real SMTP credentials.

FastAPI `BackgroundTasks` sends a notification when a user saves an opportunity. Event reminder schedules are stored in Postgres for one hour before each event. Each API request, including `/api/health`, checks for due reminders and dispatches them in the background to users who saved that company. Emails use the Jinja templates in `app/templates/email/` and are delivered through `fastapi-mail`.

The authenticated saved-role endpoint is `GET /company/saved`. The existing `PATCH /company/interested/{company_id}` endpoint toggles a saved role and queues the confirmation notification when the role becomes saved.

## Hosting on Render

The repository's `render.yaml` defines the free API, static frontend, and PostgreSQL database. Create a Blueprint from the repository in Render. The first deploy uses a fresh database; `scripts/bootstrap_db.py` creates the current schema and stamps it as the Alembic baseline, then applies future migrations normally.

Set the prompted values without committing them: `GOOGLE_CLIENT_ID`, `RVCE_EMAIL_DOMAIN`, `SPC_EMAILS`, `CORS_ORIGINS`, `VITE_GOOGLE_CLIENT_ID`, and the SMTP values. `CORS_ORIGINS` is the exact HTTPS origin of the static site, such as `https://driveboard-rvce.onrender.com`; the Google client must also allow that origin. Use the same Google Client ID for backend and frontend.

An external uptime monitor can ping `/api/health` periodically to wake the API and prompt due reminders to be sent. Postgres preserves reminder schedules across sleep and restarts, but delivery can be late if the service is asleep and an interrupted email send may be retried. Render may restart free services at any time, and its free Postgres expires after 30 days; this setup is suitable for a preview rather than reliable production delivery.
