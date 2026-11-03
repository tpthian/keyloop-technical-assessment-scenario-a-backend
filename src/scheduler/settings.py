from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://scheduler:scheduler@localhost:5432/scheduler"
    APP_ENV: str = "dev"
    LOG_LEVEL: str = "INFO"


def get_settings() -> Settings:
    return Settings()
