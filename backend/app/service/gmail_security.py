import logging

from cryptography.fernet import Fernet, InvalidToken
from google.auth.transport.urllib3 import Request
from google.oauth2 import id_token
from google.auth.transport import urllib3

from app.config.config import gmail_settings

logger = logging.getLogger(__name__)


class GmailCredentialError(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = gmail_settings.TOKEN_ENCRYPTION_KEY.strip()
    if not key:
        raise GmailCredentialError("TOKEN_ENCRYPTION_KEY is required before connecting Gmail")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as error:
        raise GmailCredentialError("TOKEN_ENCRYPTION_KEY must be a valid Fernet key") from error


def encrypt_refresh_token(token: str) -> str:
    return _fernet().encrypt(token.encode("utf-8")).decode("ascii")


def decrypt_refresh_token(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeEncodeError) as error:
        raise GmailCredentialError("Stored Gmail credentials cannot be decrypted") from error


def verify_pubsub_bearer(token: str) -> dict:
    audience = gmail_settings.GOOGLE_PUBSUB_AUDIENCE.strip()
    expected_email = gmail_settings.GOOGLE_PUBSUB_SERVICE_ACCOUNT.strip().casefold()
    if not audience or not expected_email:
        logger.error(
            "Pub/Sub authentication is missing configuration: audience_set=%s service_account_set=%s",
            bool(audience), bool(expected_email),
        )
        raise GmailCredentialError("Pub/Sub audience and service account must be configured")
    try:
        claims = id_token.verify_oauth2_token(token, Request(urllib3.PoolManager()), audience)
    except Exception as error:
        # Never log the bearer token. The verifier message identifies common
        # setup issues such as an audience mismatch without exposing credentials.
        logger.warning("Pub/Sub OIDC token verification failed: %s: %s", type(error).__name__, str(error)[:400])
        raise GmailCredentialError("Pub/Sub token is invalid") from error
    actual_email = str(claims.get("email", "")).casefold()
    email_verified = claims.get("email_verified") is True
    if actual_email != expected_email or not email_verified:
        logger.warning(
            "Pub/Sub OIDC identity mismatch: expected_service_account=%s token_service_account=%s email_verified=%s",
            expected_email, actual_email or "missing", email_verified,
        )
        raise GmailCredentialError("Pub/Sub service account is not authorized")
    return claims
