import itertools
import random
import time
from collections import OrderedDict
from collections.abc import Iterable, Iterator
from pathlib import Path

import RPi.GPIO as GPIO
from PIL import Image, ImageSequence
from pydantic import BaseModel, ConfigDict

BUTTONS = {
    "A": 5,
    "B": 6,
    "X": 16,
    "Y": 24,
}


class GifFrame(BaseModel):
    image: Image.Image
    duration: float

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)


class GifAnimation:
    def __init__(self, path, size):
        self.path = Path(path)
        self.frames = load_gif_frames(self.path, size)
        self.index = 0

    def next_frame(self):
        frame = self.frames[self.index]
        self.index = (self.index + 1) % len(self.frames)
        return frame

    def reset(self):
        self.index = 0

    def close(self):
        for frame in self.frames:
            frame.image.close()
        self.frames.clear()


class GifAnimationDeck:
    def __init__(self, paths, size, max_cached_animations=1):
        self.size = size
        self.paths = list(paths)
        self.max_cached_animations = max(max_cached_animations, 1)
        self.animation_cache = OrderedDict()
        self.path_cycle = shuffled_path_cycle(self.paths)

    def next_animation(self):
        path = next(self.path_cycle)
        animation = self.animation_cache.get(path)
        if animation is None:
            animation = GifAnimation(path, self.size)
            self.animation_cache[path] = animation
            self.evict_old_animations()
        else:
            self.animation_cache.move_to_end(path)
        animation.reset()
        return animation

    def evict_old_animations(self):
        while len(self.animation_cache) > self.max_cached_animations:
            _path, animation = self.animation_cache.popitem(last=False)
            animation.close()

    def close(self):
        for animation in self.animation_cache.values():
            animation.close()
        self.animation_cache.clear()


class ButtonPressReader:
    def __init__(self, buttons=None, debounce_seconds=0.2):
        self.buttons = buttons or BUTTONS
        self.debounce_seconds = debounce_seconds
        self.previous = {}
        self.last_pressed = {name: 0.0 for name in self.buttons}

    def setup(self):
        GPIO.setmode(GPIO.BCM)
        for pin in self.buttons.values():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.previous = {name: GPIO.input(pin) for name, pin in self.buttons.items()}

    def pressed(self):
        now = time.monotonic()
        pressed = []

        for name, pin in self.buttons.items():
            current = GPIO.input(pin)
            was_released = self.previous[name] == GPIO.HIGH
            is_pressed = current == GPIO.LOW

            if (
                was_released
                and is_pressed
                and now - self.last_pressed[name] >= self.debounce_seconds
            ):
                pressed.append(name)
                self.last_pressed[name] = now

            self.previous[name] = current

        return pressed

    def cleanup(self):
        GPIO.cleanup(list(self.buttons.values()))


def shuffled_path_cycle(paths: Iterable[Path]) -> Iterator[Path]:
    items = list(paths)
    if not items:
        raise ValueError("No GIF files found")

    previous = None
    for _ in itertools.cycle([None]):
        batch = random.sample(items, len(items))
        if previous is not None and len(batch) > 1 and batch[0] == previous:
            batch[0], batch[1] = batch[1], batch[0]

        yield from batch
        previous = batch[-1]


def gif_paths(directory):
    paths = sorted(Path(directory).glob("*.gif"))
    if not paths:
        raise ValueError(f"No GIF files found in directory: {directory}")
    return paths


def load_gif_frames(path, size):
    with Image.open(path) as gif:
        frames = []
        for frame in ImageSequence.Iterator(gif):
            duration = frame.info.get("duration", 100) / 1000
            image = frame.convert("RGB")
            try:
                if image.size != size:
                    resized = image.resize(size, Image.Resampling.LANCZOS)
                    try:
                        frame_image = resized.copy()
                    finally:
                        resized.close()
                else:
                    frame_image = image.copy()
            finally:
                image.close()
            frames.append(GifFrame(image=frame_image, duration=max(duration, 0.01)))

    if not frames:
        raise ValueError(f"GIF has no frames: {path}")

    return frames
