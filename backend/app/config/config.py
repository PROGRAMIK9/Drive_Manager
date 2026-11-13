from pathlib import Path
from pydantic_settings import BaseSettings
from urllib.parse import quote
from sqlalchemy.engine import make_url

ENV_FILE_PATH = str(Path(__file__).parent.parent.parent / ".env")

class DatabaseSetting(BaseSettings):
    DATABASE_URL: str | None = None
    POSTGRES_USERNAME: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_HOST: str = ""
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = ""

    model_config = {
        "env_file": ENV_FILE_PATH,
        "case_sensitive": True,
        "extra": "ignore"
    }
    
    @property
    def POSTGRES_URL(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = "postgresql://" + url.removeprefix("postgres://")
            return make_url(url).set(drivername="postgresql+asyncpg").render_as_string(
                hide_password=False
            )
        if not all((self.POSTGRES_USERNAME, self.POSTGRES_PASSWORD, self.POSTGRES_HOST, self.POSTGRES_DB)):
            raise ValueError("Set DATABASE_URL or all POSTGRES_* database settings")
        encoded_password = quote(self.POSTGRES_PASSWORD, safe='')
        return f"postgresql+asyncpg://{self.POSTGRES_USERNAME}:{encoded_password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


class TokenSettings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    model_config = {
        "env_file": ENV_FILE_PATH,
        "case_sensitive": True,
        "extra": "ignore"
    }

settings = DatabaseSetting()
token_settings = TokenSettings()


class GoogleAuthSettings(BaseSettings):
    GOOGLE_CLIENT_ID: str
    RVCE_EMAIL_DOMAIN: str
    SPC_EMAILS: str = ""

    model_config = {
        "env_file": ENV_FILE_PATH,
        "case_sensitive": True,
        "extra": "ignore",
    }

    @property
    def spc_emails(self) -> set[str]:
        return {
            email.strip().lower()
            for email in self.SPC_EMAILS.split(",")
            if email.strip()
        }


google_auth_settings = GoogleAuthSettings()


class AppSettings(BaseSettings):
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    FRONTEND_URL: str = "http://127.0.0.1:5173"
    SPCS_GMAIL_ADDRESS: str = "maaryamannp.mca25@rvce.edu.in"
    PLACEMENT_SENDER_DOMAIN: str = "rvce.edu.in"

    model_config = {
        "env_file": ENV_FILE_PATH,
        "case_sensitive": True,
        "extra": "ignore",
    }

    @property
    def cors_origins(self) -> list[str]:
        origins = [origin.strip().rstrip("/") for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        frontend_origin = self.FRONTEND_URL.strip().rstrip("/")
        if frontend_origin and frontend_origin not in origins:
            origins.append(frontend_origin)
        return origins


app_settings = AppSettings()


class GmailSettings(BaseSettings):
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://127.0.0.1:8000/api/integrations/gmail/callback"
    GOOGLE_PUBSUB_TOPIC: str = ""
    GOOGLE_PUBSUB_SUBSCRIPTION: str = "projects/model-arcadia-514605-a9/subscriptions/driveboard-gmail-events-sub"
    GOOGLE_PUBSUB_AUDIENCE: str = ""
    GOOGLE_PUBSUB_SERVICE_ACCOUNT: str = ""
    SPCS_GMAIL_ADDRESS: str = "maaryamannp.mca25@rvce.edu.in"
    PLACEMENT_SENDER_DOMAIN: str = "rvce.edu.in"
    TOKEN_ENCRYPTION_KEY: str = ""
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    LLM_PROVIDER: str = "groq"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = ""
    OLLAMA_TIMEOUT: int = 120

    model_config = {
        "env_file": ENV_FILE_PATH,
        "case_sensitive": True,
        "extra": "ignore",
    }


gmail_settings = GmailSettings()


class MailSettings(BaseSettings):
    BREVO_API_KEY: str = ""
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_PORT: int = 587
    MAIL_SERVER: str = ""
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    MAIL_FROM: str = ""
    MAIL_FROM_NAME: str = "Driveboard"
    VERIFICATION_URL: str = "http://localhost:8000/user/verify"
    VERIFICATION_TOKEN_EXPIRE_MINUTES: int = 60

    model_config = {
        "env_file": ENV_FILE_PATH,
        "case_sensitive": True,
        "extra": "ignore",
    }


mail_settings = MailSettings()
