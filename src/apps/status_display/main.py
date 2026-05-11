import signal
import subprocess
import time

import numpy as np
import st7789
from PIL import Image
from rich.console import Console

from src.apps.status_display.settings import settings

WIDTH = 240
HEIGHT = 240
console = Console()


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


def rainbow_frame(width, height, offset):
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)

    hue = ((xx + yy + offset) % 1.0) * 6.0
    channel = 1.0 - np.abs(hue % 2.0 - 1.0)

    red = np.select(
        [hue < 1, hue < 2, hue < 3, hue < 4, hue < 5],
        [1.0, channel, 0.0, 0.0, channel],
        default=1.0,
    )
    green = np.select(
        [hue < 1, hue < 2, hue < 3, hue < 4, hue < 5],
        [channel, 1.0, 1.0, channel, 0.0],
        default=0.0,
    )
    blue = np.select(
        [hue < 1, hue < 2, hue < 3, hue < 4, hue < 5],
        [0.0, 0.0, channel, 1.0, 1.0],
        default=channel,
    )

    rgb = np.dstack((red, green, blue))
    return Image.fromarray((rgb * 255).astype(np.uint8), "RGB")


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

    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    delay = 1.0 / settings.fps
    offset = 0.0
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
                display.display(rainbow_frame(WIDTH, HEIGHT, offset))
                offset = (offset + settings.step) % 1.0
            else:
                display.display(black)

            time.sleep(delay)
    finally:
        display.display(black)


if __name__ == "__main__":
    main()
