import signal
import time

from rich.console import Console

from src.apps.buttons_listener.settings import settings
from src.apps.utils import ButtonPressReader

console = Console()


def main():
    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    buttons = ButtonPressReader(debounce_seconds=settings.bounce_ms / 1000.0)
    buttons.setup()

    try:
        console.log("[green]Listening for Pirate Audio button events[/green]")

        poll_seconds = settings.poll_ms / 1000.0

        while running:
            for name in buttons.pressed():
                console.log(f"[cyan]Button {name} pressed[/cyan]")

            time.sleep(poll_seconds)
    finally:
        buttons.cleanup()
        console.log("[yellow]Stopped listening for button events[/yellow]")


if __name__ == "__main__":
    main()
