import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import st7789
from PIL import Image, ImageSequence
from rich.console import Console

from src.apps.status_display.settings import settings

WIDTH = 240
HEIGHT = 240
console = Console()


@dataclass(frozen=True)
class GifFrame:
    image: Image.Image
    duration: float


class GifAnimation:
    def __init__(self, path):
        self.path = Path(path)
        self.frames = load_gif_frames(self.path)
        self.index = 0

    def next_frame(self):
        frame = self.frames[self.index]
        self.index = (self.index + 1) % len(self.frames)
        return frame


class BluetoothConnectionReader:
    def __init__(self, poll_seconds):
        self.poll_seconds = poll_seconds
        self.last_poll = 0.0
        self.last_connected = False

    def connected(self):
        now = time.monotonic()
        if now - self.last_poll < self.poll_seconds:
            return self.last_connected

        self.last_poll = now
        try:
            result = subprocess.run(
                ["bluetoothctl", "devices", "Connected"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.TimeoutExpired):
            self.last_connected = False
            return self.last_connected

        if result.returncode != 0:
            self.last_connected = False
            return self.last_connected

        self.last_connected = any(
            line.startswith("Device ") for line in result.stdout.splitlines()
        )
        return self.last_connected


def load_gif_frames(path):
    with Image.open(path) as gif:
        frames = []
        for frame in ImageSequence.Iterator(gif):
            duration = frame.info.get("duration", 100) / 1000
            image = frame.convert("RGB")
            if image.size != (WIDTH, HEIGHT):
                image = image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
            frames.append(GifFrame(image.copy(), max(duration, 0.01)))

    if not frames:
        raise ValueError(f"GIF has no frames: {path}")

    return frames


def create_display(config):
    return st7789.ST7789(
        port=config.port,
        cs=config.cs,
        dc=config.dc,
        rst=config.rst,
        backlight=config.backlight,
        width=WIDTH,
        height=HEIGHT,
        rotation=config.rotation,
        spi_speed_hz=config.spi_speed_hz,
    )


def main():
    display = create_display(settings)
    bluetooth = BluetoothConnectionReader(settings.bluetooth_poll_seconds)
    waiting_animation = GifAnimation(settings.waiting_gif_path)
    connected_animation = GifAnimation(settings.connected_gif_path)

    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    black = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    was_connected = False

    try:
        while running:
            is_connected = bluetooth.connected()
            if is_connected != was_connected:
                if is_connected:
                    console.log("[green]Bluetooth connected[/green]")
                else:
                    console.log("[yellow]Bluetooth disconnected[/yellow]")
                was_connected = is_connected

            if is_connected:
                frame = connected_animation.next_frame()
            else:
                frame = waiting_animation.next_frame()

            frame_started = time.monotonic()
            display.display(frame.image)
            elapsed = time.monotonic() - frame_started
            time.sleep(max(frame.duration - elapsed, 0.0))
    finally:
        display.display(black)


if __name__ == "__main__":
    main()
