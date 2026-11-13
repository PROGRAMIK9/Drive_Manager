## Mail notifications

Mail credentials are read from environment variables. Add the values listed in `.env.example` to your local `.env`; the application does not provide defaults for real mail credentials. Set `BREVO_API_KEY` to send through Brevo's HTTPS API. When it is empty, the application uses SMTP settings instead.

FastAPI `BackgroundTasks` sends a notification when a user saves an opportunity. Event reminder schedules are stored in Postgres for one hour before each event. Each API request, including `/api/health`, checks for due reminders and dispatches them in the background to users who saved that company. Emails use the Jinja templates in `app/templates/email/` and are delivered through `fastapi-mail`.

The authenticated saved-role endpoint is `GET /company/saved`. The existing `PATCH /company/interested/{company_id}` endpoint toggles a saved role and queues the confirmation notification when the role becomes saved.

## Placement email review and Gmail integration

Driveboard has a PostgreSQL-backed SPC review queue, Gmail OAuth routes, encrypted refresh-token storage, an authenticated Pub/Sub webhook, Gmail Watch/history sync, sender filtering, hosted/local LLM extraction, and durable notification retries. RVCE-sender emails are classified and placement details are extracted into pending SPC review; every detected company is queued even if MCA eligibility is unclear or excluded. Pending opportunities publish into the existing `Company` table only after SPC approval. The company schema has one event date and one batch; approval maps the first available OA, GD, or interview date to that event date, then falls back to the department submission date, application deadline, or current time. The review queue retains OA, GD, all detected interview dates, SPC submission date, and other extracted fields.

The mailbox defaults to `maaryamannp.mca25@rvce.edu.in`; message senders must have the exact `@rvce.edu.in` domain to be considered. Other senders are stored as ignored. The authenticated Pub/Sub webhook durably queues notifications in Postgres. A lightweight task in the API process drains that queue, fetches Gmail history and messages, classifies/extracts fields with Groq (or local Ollama), creates pending SPC review items, retries failures, and renews Gmail Watch. Manual sync uses the same classification pipeline.

Gmail routes: SPC-only `POST /api/integrations/gmail/connect`, `GET /api/integrations/gmail/status`, `DELETE /api/integrations/gmail/disconnect`, `POST /api/admin/integrations/gmail/watch`, and `POST /api/admin/integrations/gmail/sync`; webhook `POST /api/webhooks/gmail`. OAuth callback state is hashed, expires after 15 minutes, and is linked to the SPC who initiated the flow. The callback verifies that the authorized Google account is exactly `SPCS_GMAIL_ADDRESS` before encrypting and saving its refresh token. Use the same Driveboard host (`localhost` or `127.0.0.1`) throughout the login and OAuth flow, and restart both services after code or `.env` changes.

## Local development

From the repository root, run `./run.sh` to start the FastAPI server on port 8000 and Vite on port 5173. It requires `uv`, Node/npm, `backend/.env`, and a reachable PostgreSQL database already configured through the current environment. The script initializes/migrates the configured database and starts the Gmail automation task with the API.

## Gmail and hosted inference setup

1. **Google Cloud project:** use a project you control, enable Gmail API and Cloud Pub/Sub API, configure the OAuth consent screen, and create a Web application OAuth client. Add the mailbox as a test user if the consent screen is in testing.
2. **OAuth values:** configure the extraction client separately as `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`. Keep `GOOGLE_CLIENT_ID` / `VITE_GOOGLE_CLIENT_ID` for normal Driveboard login. Register the exact callback URI `https://<your-api-host>/api/integrations/gmail/callback` under Authorized redirect URIs; set it as `GOOGLE_REDIRECT_URI`. The personal Google account may own the client, but the RVCE mailbox itself must sign in and consent when connecting.
3. **Gmail policy:** this app requests `gmail.readonly`, a restricted Gmail scope. Review Google's current verification and security-assessment requirements before production use. [Gmail OAuth scopes](https://developers.google.com/gmail/api/auth/scopes)
4. **Pub/Sub:** create a topic and a push subscription. Grant `gmail-api-push@system.gserviceaccount.com` the Pub/Sub Publisher role on the topic. Configure the push endpoint as `https://<your-api-host>/api/webhooks/gmail`, enable authenticated push, select a **user-managed service account in the same Google Cloud project** as the subscription, and set the OIDC audience to that exact webhook URL. Set `GOOGLE_PUBSUB_AUDIENCE` to the configured OIDC audience and `GOOGLE_PUBSUB_SERVICE_ACCOUNT` to the selected user-managed service account email. Do not put `gmail-api-push@system.gserviceaccount.com` or the Pub/Sub service agent in `GOOGLE_PUBSUB_SERVICE_ACCOUNT`; those identities have separate publishing/signing roles. The Pub/Sub service agent (`service-<PROJECT_NUMBER>@gcp-sa-pubsub.iam.gserviceaccount.com`) needs `roles/iam.serviceAccountTokenCreator` on the selected user-managed account, and the person configuring the subscription needs permission to attach it. Google also requires `gmail-api-push@system.gserviceaccount.com` to have Pub/Sub Publisher on the topic. [Gmail push setup](https://developers.google.com/workspace/gmail/api/guides/push), [authenticated push setup](https://cloud.google.com/pubsub/docs/authenticate-push-subscriptions) Add the full topic and subscription names to `GOOGLE_PUBSUB_TOPIC` and `GOOGLE_PUBSUB_SUBSCRIPTION`. The webhook validates Google's signed JWT and stores notifications durably before acknowledging them.
5. **Token encryption:** generate a Fernet key with `cd backend && .venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`. Put the same key in local `backend/.env` and Render's `TOKEN_ENCRYPTION_KEY`. Keep a secure backup; losing the key makes stored refresh tokens unreadable. Never commit it.
6. **Groq:** create a server-side key at [Groq API keys](https://console.groq.com/keys). Set `LLM_PROVIDER=groq`, `GROQ_API_KEY`, and `GROQ_MODEL` in the backend only. The model receives the sender, subject, received time, and email body to prepare a draft for human SPC review. Confirm college policy before sending email text to hosted inference. [Groq JSON mode](https://console.groq.com/docs/structured-outputs)
7. **Render free service:** the API includes the durable job loop; no separate worker or Redis service is required. Configure the Pub/Sub push URL as `https://driveboard-api.onrender.com/api/webhooks/gmail` (or your API's actual URL) and use the same exact URL as the authenticated push audience. Render does not use Google Cloud IAM to authorize this endpoint; the app verifies the signed Pub/Sub OIDC token itself. Render Free web services spin down after 15 minutes without inbound traffic, so notifications may wait for a cold start; persisted Pub/Sub delivery and the Postgres queue allow processing after the service wakes. Configure an external uptime monitor to ping `/api/health` at least daily so the sleeping service wakes often enough to renew Gmail Watch; Gmail requires renewing at least every 7 days and recommends daily renewal. This is best-effort automation rather than an always-on SLA. [Render free service behavior](https://render.com/docs/free)

Never share API keys, OAuth secrets, refresh tokens, or encryption keys in chat. If a real key was accidentally pasted into a tracked file or chat, revoke and replace it.

## Hosted LLM choice

For the current Render hosting plan, a hosted inference API is a better fit than running local Ollama on the same web service: local inference needs persistent compute and often GPU/RAM resources that a small web instance does not provide. The extraction interface should remain provider-neutral. Groq exposes an OpenAI-compatible API at `https://api.groq.com/openai/v1`; Ollama Cloud is another hosted open-model option with usage-based pricing/credits. Compare the currently available models, rate limits, and data terms before choosing. For college placement mail, start with minimized email text (remove signatures and unrelated thread history), no automatic publishing, and human SPC review. This recommendation is deployment-specific; if a GPU server is later provisioned, self-hosted Ollama remains a valid option.

## SPC notifications

When an SPC adds a company through the existing company API, other registered SPC accounts receive an email through the existing configured mail provider. The person adding the company is excluded from recipients. Delivery depends on `BREVO_API_KEY` or the existing SMTP settings being configured.

To apply the new review schema, run the existing migration workflow from `backend` after installing dependencies and configuring the existing database environment:

```sh
uv run alembic upgrade head
```

SPC review API routes use the existing bearer token and `SPC` role. The endpoints are `GET /api/admin/placement/pending/`, `GET /api/admin/placement/pending/{id}`, `PATCH /api/admin/placement/pending/{id}`, and the `/approve` and `/reject` actions.

## Hosting on Render

The repository's `render.yaml` defines the free API, static frontend, and PostgreSQL database. Create a Blueprint from the repository in Render. The first deploy uses a fresh database; `scripts/bootstrap_db.py` creates the current schema and stamps it as the Alembic baseline, then applies future migrations normally.

Set the prompted values without committing them: `GOOGLE_CLIENT_ID`, `RVCE_EMAIL_DOMAIN`, `SPC_EMAILS`, `CORS_ORIGINS`, `VITE_GOOGLE_CLIENT_ID`, `BREVO_API_KEY`, and `MAIL_FROM`. For a free Render web service, use Brevo's HTTPS API: Render blocks outbound SMTP on ports 25, 465, and 587. Create a Brevo API key and set it as `BREVO_API_KEY`; set `MAIL_FROM` to an address registered and verified as a sender in Brevo. `MAIL_FROM_NAME` is optional. `CORS_ORIGINS` is the exact HTTPS origin of the static site, such as `https://driveboard-rvce.onrender.com`; the Google client must also allow that origin. Use the same Google Client ID for backend and frontend.

An external uptime monitor can ping `/api/health` periodically to wake the API and prompt due reminders to be sent. Postgres preserves reminder schedules across sleep and restarts, but delivery can be late if the service is asleep and an interrupted email send may be retried. Render may restart free services at any time, and its free Postgres expires after 30 days; this setup is suitable for a preview rather than reliable production delivery.
