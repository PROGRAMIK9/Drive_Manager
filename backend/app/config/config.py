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