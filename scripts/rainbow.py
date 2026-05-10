import argparse
import signal
import time

import numpy as np
from PIL import Image
import st7789


WIDTH = 240
HEIGHT = 240


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


def create_display(args):
    return st7789.ST7789(
        port=args.port,
        cs=args.cs,
        dc=args.dc,
        rst=args.rst,
        backlight=args.backlight,
        width=WIDTH,
        height=HEIGHT,
        rotation=args.rotation,
        spi_speed_hz=args.spi_speed_hz,
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Run a rainbow animation on Pirate Audio.")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--cs", type=int, default=1)
    parser.add_argument("--dc", type=int, default=9)
    parser.add_argument("--rst", type=int, default=25)
    parser.add_argument("--backlight", type=int, default=13)
    parser.add_argument("--rotation", type=int, default=90)
    parser.add_argument("--spi-speed-hz", type=int, default=80 * 1000 * 1000)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--step", type=float, default=0.01)
    return parser.parse_args()


def main():
    args = parse_args()
    display = create_display(args)

    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    delay = 1.0 / args.fps
    offset = 0.0

    while running:
        display.display(rainbow_frame(WIDTH, HEIGHT, offset))
        offset = (offset + args.step) % 1.0
        time.sleep(delay)


if __name__ == "__main__":
    main()
