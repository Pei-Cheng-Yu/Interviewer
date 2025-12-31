import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    # Optional: allow overriding everything with a single URL (best for Cloud Run)
    DATABASE_URL: str | None = os.getenv("DATABASE_URL")

    # Defaults for local docker-compose
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "pass")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "db")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")

    @property
    def db_url(self) -> str:
        # 1) Cloud Run / production: use full DATABASE_URL if provided
        if self.DATABASE_URL:
            return self.DATABASE_URL

        # 2) Local compose fallback
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
