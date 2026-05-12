from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    port: int = 0
    cs: int = 1
    dc: int = 9
    rst: int | None = None
    backlight: int = 13
    rotation: int = 90
    spi_speed_hz: int = 80 * 1000 * 1000
    fps: float = 30.0
    step: float = 0.01
    bluetooth_poll_seconds: float = 0.25
    gif_directory: str = "gif"
    max_cached_animations: int = 1


settings = Settings()
