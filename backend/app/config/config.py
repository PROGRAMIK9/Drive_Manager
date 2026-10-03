from pathlib import Path
from pydantic_settings import BaseSettings
from urllib.parse import quote

ENV_FILE_PATH = str(Path(__file__).parent.parent.parent / ".env")

class DatabaseSetting(BaseSettings):
    POSTGRES_USERNAME: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB: str

    model_config = {
        "env_file": ENV_FILE_PATH,
        "case_sensitive": True,
        "extra": "ignore"
    }
    
    @property
    def POSTGRES_URL(self) -> str:
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


class MailSettings(BaseSettings):
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


class CelerySettings(BaseSettings):
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    model_config = {
        "env_file": ENV_FILE_PATH,
        "case_sensitive": True,
        "extra": "ignore",
    }


mail_settings = MailSettings()
celery_settings = CelerySettings()