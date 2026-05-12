import signal
import subprocess
import time

import st7789
from PIL import Image
from rich.console import Console

from src.apps.status_display.settings import settings
from src.apps.utils import ButtonPressReader, GifAnimationDeck, gif_paths

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
    buttons = ButtonPressReader()

    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    black = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    was_connected = False
    animation_deck = None

    try:
        buttons.setup()
        animation_deck = GifAnimationDeck(
            gif_paths(settings.gif_directory),
            size=(WIDTH, HEIGHT),
            max_cached_animations=settings.max_cached_animations,
        )
        current_animation = animation_deck.next_animation()
        console.log(f"Showing animation: {current_animation.path}")

        while running:
            is_connected = bluetooth.connected()
            if is_connected != was_connected:
                if is_connected:
                    console.log("[green]Bluetooth connected[/green]")
                else:
                    console.log("[yellow]Bluetooth disconnected[/yellow]")
                was_connected = is_connected
                current_animation = animation_deck.next_animation()
                console.log(f"Showing animation: {current_animation.path}")

            pressed_buttons = buttons.pressed()
            if pressed_buttons:
                console.log(f"[cyan]Button {', '.join(pressed_buttons)} pressed[/cyan]")
                current_animation = animation_deck.next_animation()
                console.log(f"Showing animation: {current_animation.path}")

            frame = current_animation.next_frame()

            frame_started = time.monotonic()
            display.display(frame.image)
            elapsed = time.monotonic() - frame_started
            time.sleep(max(frame.duration - elapsed, 0.0))
    finally:
        display.display(black)
        if animation_deck is not None:
            animation_deck.close()
        buttons.cleanup()


if __name__ == "__main__":
    main()
