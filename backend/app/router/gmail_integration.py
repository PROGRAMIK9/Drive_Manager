import base64
import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import httpx
from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select

from app.config.config import app_settings, gmail_settings
from app.database.database import SessionDep
from app.schema.database import GmailIntegration, GmailOAuthState, Role, User
from app.schema.models import GmailStatusRead
from app.service.gmail_security import GmailCredentialError, decrypt_refresh_token, encrypt_refresh_token, verify_pubsub_bearer
from app.service.gmail_automation import (
    enqueue_gmail_notification,
    run_manual_mailbox_sync,
    run_manual_watch_renewal,
)
from app.service.user_services import CurrentUserDep

router = APIRouter(tags=["Gmail integration"])
logger = logging.getLogger(__name__)
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def _require_spc(user) -> None:
    if user.role != Role.spc:
        raise HTTPException(status_code=403, detail="Only SPC users can manage Gmail integration")


def _require_oauth_configuration() -> None:
    if not gmail_settings.GOOGLE_OAUTH_CLIENT_ID or not gmail_settings.GOOGLE_OAUTH_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Gmail OAuth client is not configured")


@router.post("/api/integrations/gmail/connect")
async def connect_gmail(session: SessionDep, user: CurrentUserDep):
    _require_spc(user)
    _require_oauth_configuration()
    if not gmail_settings.TOKEN_ENCRYPTION_KEY:
        raise HTTPException(status_code=503, detail="Gmail token encryption is not configured")
    state = secrets.token_urlsafe(32)
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    await session.execute(delete(GmailOAuthState).where(GmailOAuthState.created_at < datetime.now(timezone.utc) - timedelta(minutes=15)))
    session.add(GmailOAuthState(state_hash=state_hash, user_id=user.id))
    await session.commit()
    logger.warning("Gmail OAuth state saved user_id=%s state_hash_prefix=%s", user.id, state_hash[:10])
    from urllib.parse import urlencode
    params = urlencode({
        "client_id": gmail_settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": gmail_settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": f"openid email {GMAIL_SCOPE}",
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    })
    return {"authorization_url": f"https://accounts.google.com/o/oauth2/v2/auth?{params}"}


@router.get("/api/integrations/gmail/callback")
async def gmail_callback(
    session: SessionDep,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    if error:
        raise HTTPException(status_code=400, detail="Gmail authorization was not completed")
    if not state or not code:
        raise HTTPException(status_code=400, detail="OAuth code or state is missing")
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    stored_state = await session.scalar(select(GmailOAuthState).where(GmailOAuthState.state_hash == state_hash))
    if not stored_state:
        logger.warning("Gmail OAuth callback state not found state_hash_prefix=%s", state_hash[:10])
        raise HTTPException(
            status_code=400,
            detail="OAuth state was not found in this database. Start Gmail connection again from this Driveboard instance.",
        )
    # PostgreSQL returns timezone-aware values; SQLite may return a naive
    # datetime for the same timezone=True column, so normalize before comparing.
    state_created_at = stored_state.created_at
    if state_created_at.tzinfo is None:
        state_created_at = state_created_at.replace(tzinfo=timezone.utc)
    if state_created_at < datetime.now(timezone.utc) - timedelta(minutes=15):
        logger.warning("Gmail OAuth callback state expired state_hash_prefix=%s", state_hash[:10])
        await session.delete(stored_state)
        await session.commit()
        raise HTTPException(status_code=400, detail="OAuth state is invalid or expired; start Gmail connection again")
    state_user = await session.get(User, stored_state.user_id)
    if not state_user or state_user.role != Role.spc:
        logger.warning("Gmail OAuth callback state has no active SPC state_hash_prefix=%s", state_hash[:10])
        await session.delete(stored_state)
        await session.commit()
        raise HTTPException(status_code=403, detail="SPC authorization expired; start Gmail connection again")
    if not gmail_settings.TOKEN_ENCRYPTION_KEY:
        logger.error("Gmail OAuth callback cannot continue: token encryption key is not configured")
        await session.delete(stored_state)
        await session.commit()
        raise HTTPException(status_code=503, detail="Gmail token encryption is not configured")
    await session.execute(delete(GmailOAuthState).where(GmailOAuthState.id == stored_state.id))
    await session.commit()
    _require_oauth_configuration()
    async with httpx.AsyncClient(timeout=20) as client:
        token_response = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": gmail_settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": gmail_settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": gmail_settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        if token_response.is_error:
            await session.rollback()
            raise HTTPException(status_code=502, detail="Google token exchange failed")
        tokens = token_response.json()
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        if not access_token or not refresh_token:
            await session.rollback()
            raise HTTPException(status_code=502, detail="Google did not return offline mailbox credentials")
        user_response = await client.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        if user_response.is_error:
            await session.rollback()
            raise HTTPException(status_code=502, detail="Could not verify the connected Google account")
        account = user_response.json()

    expected = gmail_settings.SPCS_GMAIL_ADDRESS.strip().casefold()
    connected = str(account.get("email", "")).strip().casefold()
    if not account.get("email_verified") or connected != expected:
        await session.rollback()
        raise HTTPException(status_code=403, detail=f"Authorize the configured mailbox {expected}")
    try:
        encrypted = encrypt_refresh_token(refresh_token)
    except GmailCredentialError as exc:
        await session.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    integration = await session.scalar(select(GmailIntegration).where(GmailIntegration.connected.is_(True)))
    now = datetime.now(timezone.utc)
    if integration is None:
        integration = GmailIntegration(email_address=connected, connected=True, encrypted_refresh_token=encrypted)
        session.add(integration)
    else:
        integration.email_address = connected
        integration.connected = True
        integration.encrypted_refresh_token = encrypted
        integration.updated_at = now
    await session.commit()
    try:
        await run_manual_watch_renewal(session, integration)
    except Exception as exc:
        await session.rollback()
        integration = await session.scalar(select(GmailIntegration).where(GmailIntegration.connected.is_(True)))
        if integration:
            integration.last_error = f"Gmail connected, but automatic watch setup failed: {str(exc)[:1700]}"
            await session.commit()
    return RedirectResponse(f"{app_settings.FRONTEND_URL.rstrip('/')}/?gmail=connected", status_code=303)


@router.get("/api/integrations/gmail/status", response_model=GmailStatusRead)
async def gmail_status(session: SessionDep, user: CurrentUserDep):
    _require_spc(user)
    integration = await session.scalar(select(GmailIntegration).where(GmailIntegration.connected.is_(True)))
    if not integration:
        return GmailStatusRead(connected=False)
    return GmailStatusRead(
        connected=True,
        email_address=integration.email_address,
        last_sync_at=integration.last_sync_at,
        watch_expiration=integration.watch_expiration,
        last_error=integration.last_error,
    )


@router.delete("/api/integrations/gmail/disconnect")
async def disconnect_gmail(session: SessionDep, user: CurrentUserDep):
    _require_spc(user)
    integration = await session.scalar(select(GmailIntegration).where(GmailIntegration.connected.is_(True)))
    if not integration:
        return {"detail": "Gmail is already disconnected"}
    try:
        refresh_token = decrypt_refresh_token(integration.encrypted_refresh_token)
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post("https://oauth2.googleapis.com/revoke", data={"token": refresh_token})
    except Exception:
        pass
    integration.connected = False
    integration.encrypted_refresh_token = None
    integration.last_error = None
    integration.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return {"detail": "Gmail mailbox disconnected"}


@router.post("/api/admin/integrations/gmail/watch")
async def configure_gmail_watch(session: SessionDep, user: CurrentUserDep):
    _require_spc(user)
    integration = await session.scalar(select(GmailIntegration).where(GmailIntegration.connected.is_(True)))
    if not integration:
        raise HTTPException(status_code=409, detail="Connect the Gmail mailbox first")
    try:
        result = await run_manual_watch_renewal(session, integration)
    except Exception:
        await session.rollback()
        raise
    return {"connected": True, **result}


@router.post("/api/admin/integrations/gmail/sync")
async def sync_gmail_mailbox(session: SessionDep, user: CurrentUserDep):
    _require_spc(user)
    integration = await session.scalar(select(GmailIntegration).where(GmailIntegration.connected.is_(True)))
    if not integration:
        raise HTTPException(status_code=409, detail="Connect the Gmail mailbox first")
    try:
        result = await run_manual_mailbox_sync(session, integration)
    except Exception as exc:
        await session.rollback()
        integration.last_error = str(exc)[:2000]
        await session.commit()
        raise
    return result


@router.post("/api/webhooks/gmail")
async def gmail_pubsub_webhook(
    payload: dict,
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
):
    bearer = (authorization or "").removeprefix("Bearer ").strip()
    if not bearer:
        raise HTTPException(status_code=401, detail="Pub/Sub authentication is required")
    try:
        verify_pubsub_bearer(bearer)
    except GmailCredentialError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    message = payload.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("data"), str) or not message.get("messageId"):
        raise HTTPException(status_code=400, detail="Malformed Pub/Sub message")
    try:
        decoded = json.loads(base64.b64decode(message["data"], validate=True))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Malformed Gmail notification data") from exc
    if not isinstance(decoded, dict) or not decoded.get("emailAddress") or not decoded.get("historyId"):
        raise HTTPException(status_code=400, detail="Gmail notification is missing mailbox data")
    if str(decoded["emailAddress"]).casefold() != gmail_settings.SPCS_GMAIL_ADDRESS.casefold():
        raise HTTPException(status_code=400, detail="Notification is for an unexpected mailbox")
    created = await enqueue_gmail_notification(
        session,
        pubsub_message_id=str(message["messageId"]),
        email_address=str(decoded["emailAddress"]).casefold(),
        history_id=str(decoded["historyId"]),
    )
    return {"received": True, "queued": created, "duplicate": not created}
