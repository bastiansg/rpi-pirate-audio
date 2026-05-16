import signal
import subprocess
import time

import st7789
from PIL import Image
from rich.console import Console

from src.apps.status_display.settings import settings
from src.apps.status_display.utils import ButtonPressReader, GifAnimationDeck, gif_paths

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
        except OSError, subprocess.TimeoutExpired:
            self.last_connected = False
            return self.last_connected

        if result.returncode != 0:
            self.last_connected = False
            return self.last_connected

        self.last_connected = any(
            line.startswith("Device ") for line in result.stdout.splitlines()
        )
        return self.last_connected


class AudioVolumeController:
    def __init__(self, step, min_volume, max_volume):
        self.step = step
        self.min_volume = min_volume
        self.max_volume = max_volume

    def decrease(self):
        return self.adjust(-self.step)

    def increase(self):
        return self.adjust(self.step)

    def adjust(self, delta):
        volume = self.current_volume()
        if volume is None:
            return None

        next_volume = min(max(volume + delta, self.min_volume), self.max_volume)
        try:
            subprocess.run(
                ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{next_volume:.2f}"],
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except OSError, subprocess.SubprocessError:
            return None

        return next_volume

    def current_volume(self):
        try:
            result = subprocess.run(
                ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except OSError, subprocess.TimeoutExpired:
            return None

        if result.returncode != 0:
            return None

        for part in result.stdout.split():
            try:
                return float(part)
            except ValueError:
                continue

        return None


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
    volume = AudioVolumeController(
        step=settings.volume_step,
        min_volume=settings.min_volume,
        max_volume=settings.max_volume,
    )
    buttons = ButtonPressReader(debounce_seconds=settings.button_debounce_seconds)

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
        console.log(f"showing animation: {current_animation.path}")

        while running:
            is_connected = bluetooth.connected()
            if is_connected != was_connected:
                if is_connected:
                    console.log("[green]bluetooth connected[/green]")
                else:
                    console.log("[yellow]bluetooth disconnected[/yellow]")
                was_connected = is_connected
                current_animation = animation_deck.next_animation()
                console.log(f"showing animation: {current_animation.path}")

            pressed_buttons = buttons.pressed()
            if pressed_buttons:
                console.log(f"[cyan]button {', '.join(pressed_buttons)} pressed[/cyan]")
                for name in pressed_buttons:
                    if name == "A":
                        new_volume = volume.decrease()
                        if new_volume is None:
                            console.log("[red]could not decrease volume[/red]")
                        else:
                            console.log(
                                f"[green]volume decreased to {new_volume:.2f}[/green]"
                            )
                    elif name == "B":
                        new_volume = volume.increase()
                        if new_volume is None:
                            console.log("[red]could not increase volume[/red]")
                        else:
                            console.log(
                                f"[green]volume increased to {new_volume:.2f}[/green]"
                            )
                    elif name == "X":
                        current_animation = animation_deck.previous_animation()
                        console.log(f"showing animation: {current_animation.path}")
                    elif name == "Y":
                        current_animation = animation_deck.next_animation()
                        console.log(f"showing animation: {current_animation.path}")
                    else:
                        console.log(f"[yellow]button {name} has no action[/yellow]")

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
