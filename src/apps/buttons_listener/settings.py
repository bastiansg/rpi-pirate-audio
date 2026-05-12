from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bounce_ms: int = Field(default=200, alias="BUTTONS_BOUNCE_MS")
    poll_ms: int = Field(default=20, alias="BUTTONS_POLL_MS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
