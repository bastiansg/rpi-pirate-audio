import signal
import time

import RPi.GPIO as GPIO
from rich.console import Console

from src.apps.buttons_listener.settings import settings

BUTTONS = {
    "A": 5,
    "B": 6,
    "X": 16,
    "Y": 24,
}

console = Console()


def main():
    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    GPIO.setmode(GPIO.BCM)

    try:
        for pin in BUTTONS.values():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        console.log("[green]Listening for Pirate Audio button events[/green]")

        previous = {name: GPIO.input(pin) for name, pin in BUTTONS.items()}
        last_pressed = {name: 0.0 for name in BUTTONS}
        debounce_seconds = settings.bounce_ms / 1000.0
        poll_seconds = settings.poll_ms / 1000.0

        while running:
            now = time.monotonic()

            for name, pin in BUTTONS.items():
                current = GPIO.input(pin)
                was_released = previous[name] == GPIO.HIGH
                is_pressed = current == GPIO.LOW

                if (
                    was_released
                    and is_pressed
                    and now - last_pressed[name] >= debounce_seconds
                ):
                    console.log(f"[cyan]Button {name} pressed[/cyan]")
                    last_pressed[name] = now

                previous[name] = current

            time.sleep(poll_seconds)
    finally:
        GPIO.cleanup()
        console.log("[yellow]Stopped listening for button events[/yellow]")


if __name__ == "__main__":
    main()
