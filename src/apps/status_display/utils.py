import random
import time
from collections import OrderedDict
from pathlib import Path

import RPi.GPIO as GPIO
from PIL import Image
from pydantic import BaseModel, ConfigDict

BUTTONS = {
    "A": 5,
    "B": 6,
    "X": 16,
    "Y": 24,
}


class AnimationFrame(BaseModel):
    image: Image.Image
    duration: float

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)


class FrameAnimation:
    def __init__(self, path, frame_duration):
        self.path = Path(path)
        paths = sorted(self.path.glob("*.png"))
        if not paths:
            raise ValueError(f"No PNG frames found in directory: {self.path}")
        self.frames = tuple(load_png_frame(path, frame_duration) for path in paths)
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


class FrameAnimationDeck:
    def __init__(self, paths, frame_duration, max_cached_animations=1):
        self.paths = list(paths)
        if not self.paths:
            raise ValueError("No frame directories found")
        random.shuffle(self.paths)
        self.index = -1
        self.frame_duration = frame_duration
        self.max_cached_animations = max(max_cached_animations, 1)
        self.animation_cache = OrderedDict()

    def next_animation(self):
        self.index = (self.index + 1) % len(self.paths)
        return self.current_animation()

    def previous_animation(self):
        self.index = (self.index - 1) % len(self.paths)
        return self.current_animation()

    def current_animation(self):
        path = self.paths[self.index]
        animation = self.animation_cache.get(path)
        if animation is None:
            while len(self.animation_cache) >= self.max_cached_animations:
                _path, old_animation = self.animation_cache.popitem(last=False)
                old_animation.close()
            animation = FrameAnimation(path, self.frame_duration)
            self.animation_cache[path] = animation
        else:
            self.animation_cache.move_to_end(path)
        animation.reset()
        return animation

    def close(self):
        for animation in self.animation_cache.values():
            animation.close()
        self.animation_cache.clear()


def load_png_frame(path, duration):
    with Image.open(path) as image:
        return AnimationFrame(image=image.copy(), duration=duration)


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
        time.sleep(0.05)
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


def frame_directories(directory):
    paths = sorted(path for path in Path(directory).iterdir() if path.is_dir())
    if not paths:
        raise ValueError(f"No frame directories found in directory: {directory}")
    return paths
