from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # DB
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/app"

    # Celery
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    # Files
    MEDIA_ROOT: str = "/data/media"

    # Security
    SECRET_KEY: str = "dev-insecure-secret"
    PRESIGN_TTL_SECONDS: int = 600

    class Config:
        env_file = ".env"


settings = Settings()
