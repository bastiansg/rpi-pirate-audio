from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    port: int = Field(default=0, alias="APP_PORT")
    cs: int = Field(default=1, alias="APP_CS")
    dc: int = Field(default=9, alias="APP_DC")
    rst: int | None = Field(default=None, alias="APP_RST")
    backlight: int = Field(default=13, alias="APP_BACKLIGHT")
    rotation: int = Field(default=90, alias="APP_ROTATION")
    spi_speed_hz: int = Field(default=80 * 1000 * 1000, alias="APP_SPI_SPEED_HZ")
    fps: float = Field(default=30.0, alias="APP_FPS")
    step: float = Field(default=0.01, alias="APP_STEP")
    bluetooth_poll_seconds: float = Field(
        default=0.25, alias="APP_BLUETOOTH_POLL_SECONDS"
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
