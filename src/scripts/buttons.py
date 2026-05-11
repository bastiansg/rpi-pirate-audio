import argparse
import signal
import time

import RPi.GPIO as GPIO

BUTTONS = {
    "A": 5,
    "B": 6,
    "X": 16,
    "Y": 24,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Test Pirate Audio buttons.")
    parser.add_argument("--bounce-ms", type=int, default=200)
    parser.add_argument("--poll-ms", type=int, default=20)
    return parser.parse_args()


def main():
    args = parse_args()
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

        print("Press Pirate Audio buttons A, B, X, or Y. Ctrl+C to stop.", flush=True)

        previous = {name: GPIO.input(pin) for name, pin in BUTTONS.items()}
        last_pressed = {name: 0.0 for name in BUTTONS}
        debounce_seconds = args.bounce_ms / 1000.0
        poll_seconds = args.poll_ms / 1000.0

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
                    print(f"{name} pressed", flush=True)
                    last_pressed[name] = now

                previous[name] = current

            time.sleep(poll_seconds)
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
