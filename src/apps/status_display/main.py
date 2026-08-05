import re
import signal
import subprocess
import threading
import time

import st7789
from PIL import Image
from rich.console import Console

from src.apps.status_display.settings import settings
from src.apps.status_display.utils import (
    ButtonPressReader,
    FrameAnimationDeck,
    frame_directories,
)

WIDTH = 240
HEIGHT = 240
console = Console()


class BluetoothConnectionReader:
    connected_pattern = re.compile(
        r"Device (?P<address>(?:[0-9A-F]{2}:){5}[0-9A-F]{2}) Connected: "
        r"(?P<connected>yes|no)"
    )

    def __init__(self):
        self.connected_devices = set()
        self.lock = threading.Lock()
        self.monitor = subprocess.Popen(
            ["bluetoothctl", "--monitor"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self.connected_devices.update(self.read_connected_devices())
        self.thread = threading.Thread(target=self.read_events, daemon=True)
        self.thread.start()

    def connected(self):
        with self.lock:
            return bool(self.connected_devices)

    def read_connected_devices(self):
        try:
            result = subprocess.run(
                ["bluetoothctl", "devices", "Connected"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except OSError, subprocess.TimeoutExpired:
            return set()

        if result.returncode != 0:
            return set()

        return {
            parts[1]
            for line in result.stdout.splitlines()
            if line.startswith("Device ") and len(parts := line.split(maxsplit=2)) == 3
        }

    def read_events(self):
        if self.monitor.stdout is None:
            return

        for line in self.monitor.stdout:
            match = self.connected_pattern.search(line)
            if match is None:
                continue

            address = match.group("address")
            with self.lock:
                if match.group("connected") == "yes":
                    self.connected_devices.add(address)
                else:
                    self.connected_devices.discard(address)

    def close(self):
        if self.monitor.stdin is not None:
            self.monitor.stdin.close()
        if self.monitor.poll() is None:
            self.monitor.terminate()
        try:
            self.monitor.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.monitor.kill()
            self.monitor.wait()
        self.thread.join(timeout=2)


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
    bluetooth = BluetoothConnectionReader()
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
        animation_deck = FrameAnimationDeck(
            frame_directories(settings.frames_directory),
            frame_duration=settings.frame_duration,
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

            frame_started = time.monotonic()
            frame = current_animation.next_frame()
            display.display(frame.image)
            elapsed = time.monotonic() - frame_started
            time.sleep(max(frame.duration - elapsed, 0.0))
    finally:
        bluetooth.close()
        display.display(black)
        if animation_deck is not None:
            animation_deck.close()
        buttons.cleanup()


if __name__ == "__main__":
    main()
