"""
desktop_pet.animation.idle
=============================

Small, self-contained "idle" animation generators that make a
perfectly still pet look alive: continuous breathing, occasional
blinks, and occasional sway.

Each class is deliberately Qt-independent — they only do arithmetic on
plain floats and know nothing about widgets, pixmaps, or windows. This
keeps them trivially unit-testable (no ``QApplication`` required) and
reusable by any future rendering approach. ``ui.pet_window.PetWindow``
is what wires their output into actual on-screen motion.

All three classes share the same shape:

- ``advance(delta_time)`` moves the animation forward by
  ``delta_time`` seconds, called once per frame.
- One or more read-only properties expose the current visual value
  for the caller to apply (a pixel offset, a scale factor, a rotation
  in degrees).

Randomized timing (blinks, sway) never uses a fixed interval — each
class re-rolls its own next wait time, uniformly, within a min/max
range, every time an event finishes.
"""

from __future__ import annotations

import math
import random


class BreathingAnimation:
    """A continuous, cheap 'breathing' motion.

    Produces a small sinusoidal vertical offset so the pet's whole
    body gently rises and falls, forever, without any per-frame
    branching or scheduling — just a sine wave driven by elapsed time.
    """

    def __init__(self, amplitude_px: float = 3.0, period_seconds: float = 3.6) -> None:
        """
        Args:
            amplitude_px: Peak vertical displacement in pixels (the
                offset ranges over ``[-amplitude_px, +amplitude_px]``).
                2–4px reads as a subtle breath without looking like a
                bounce.
            period_seconds: How long one full breathing cycle takes.
                ~3.6s approximates a slow, resting breathing rate.
        """
        if amplitude_px < 0:
            raise ValueError("amplitude_px must not be negative")
        if period_seconds <= 0:
            raise ValueError("period_seconds must be positive")

        self._amplitude_px = amplitude_px
        self._angular_speed = (2.0 * math.pi) / period_seconds
        self._elapsed_seconds = 0.0

    def advance(self, delta_time: float) -> None:
        """Move the breathing cycle forward by ``delta_time`` seconds."""
        self._elapsed_seconds += delta_time

    @property
    def offset_px(self) -> float:
        """Current vertical offset in pixels (positive = further down)."""
        return self._amplitude_px * math.sin(self._elapsed_seconds * self._angular_speed)


class BlinkScheduler:
    """Randomly schedules brief, natural-feeling blinks.

    Waits a random ``[min_wait_seconds, max_wait_seconds]`` interval,
    then triggers a blink lasting a random
    ``[min_duration_seconds, max_duration_seconds]``, exposed as a
    vertical squash factor (``scale_y``) for the caller to apply to the
    sprite. Once the blink ends, a fresh random wait is rolled — timing
    never repeats on a fixed cadence.
    """

    def __init__(
        self,
        min_wait_seconds: float = 4.0,
        max_wait_seconds: float = 10.0,
        min_duration_seconds: float = 0.12,
        max_duration_seconds: float = 0.18,
        squash_scale_y: float = 0.85,
        rng: random.Random | None = None,
    ) -> None:
        """
        Args:
            min_wait_seconds: Shortest possible gap between blinks.
            max_wait_seconds: Longest possible gap between blinks.
            min_duration_seconds: Shortest possible blink duration.
            max_duration_seconds: Longest possible blink duration.
            squash_scale_y: Vertical scale factor applied while
                blinking (1.0 = no squash; smaller = more pinched).
            rng: Optional ``random.Random`` instance for deterministic
                testing. Defaults to a fresh, unseeded instance.
        """
        if min_wait_seconds <= 0 or max_wait_seconds < min_wait_seconds:
            raise ValueError("Require 0 < min_wait_seconds <= max_wait_seconds")
        if min_duration_seconds <= 0 or max_duration_seconds < min_duration_seconds:
            raise ValueError("Require 0 < min_duration_seconds <= max_duration_seconds")

        self._min_wait_seconds = min_wait_seconds
        self._max_wait_seconds = max_wait_seconds
        self._min_duration_seconds = min_duration_seconds
        self._max_duration_seconds = max_duration_seconds
        self._squash_scale_y = squash_scale_y
        self._rng = rng if rng is not None else random.Random()

        self._time_until_next_blink = self._roll_wait()
        self._is_blinking = False
        self._blink_time_remaining = 0.0

    def _roll_wait(self) -> float:
        return self._rng.uniform(self._min_wait_seconds, self._max_wait_seconds)

    def _roll_duration(self) -> float:
        return self._rng.uniform(self._min_duration_seconds, self._max_duration_seconds)

    def advance(self, delta_time: float) -> None:
        """Move the blink schedule forward by ``delta_time`` seconds."""
        if self._is_blinking:
            self._blink_time_remaining -= delta_time
            if self._blink_time_remaining <= 0.0:
                self._is_blinking = False
                self._time_until_next_blink = self._roll_wait()
        else:
            self._time_until_next_blink -= delta_time
            if self._time_until_next_blink <= 0.0:
                self._is_blinking = True
                self._blink_time_remaining = self._roll_duration()

    @property
    def is_blinking(self) -> bool:
        """Whether a blink is in progress right now."""
        return self._is_blinking

    @property
    def scale_y(self) -> float:
        """Vertical scale to apply to the sprite: 1.0 normally, dips to
        ``squash_scale_y`` while blinking."""
        return self._squash_scale_y if self._is_blinking else 1.0


class SwayAnimation:
    """Randomly schedules brief, natural-feeling tilts/sways.

    Waits a random ``[min_wait_seconds, max_wait_seconds]`` interval,
    then eases into a small random rotation (up to
    ``max_tilt_degrees`` in either direction) and back out over
    ``sway_duration_seconds``, using a smooth half-sine ease so there's
    no sudden start or stop. Once the sway ends, a fresh random wait
    and a fresh random tilt direction/magnitude are rolled.
    """

    def __init__(
        self,
        min_wait_seconds: float = 8.0,
        max_wait_seconds: float = 20.0,
        max_tilt_degrees: float = 3.0,
        sway_duration_seconds: float = 1.2,
        rng: random.Random | None = None,
    ) -> None:
        """
        Args:
            min_wait_seconds: Shortest possible gap between sways.
            max_wait_seconds: Longest possible gap between sways.
            max_tilt_degrees: Maximum rotation magnitude in either
                direction (the requirement caps this at 3°).
            sway_duration_seconds: How long one ease-in-and-back sway
                takes from start to returning to upright.
            rng: Optional ``random.Random`` instance for deterministic
                testing. Defaults to a fresh, unseeded instance.
        """
        if min_wait_seconds <= 0 or max_wait_seconds < min_wait_seconds:
            raise ValueError("Require 0 < min_wait_seconds <= max_wait_seconds")
        if max_tilt_degrees < 0:
            raise ValueError("max_tilt_degrees must not be negative")
        if sway_duration_seconds <= 0:
            raise ValueError("sway_duration_seconds must be positive")

        self._min_wait_seconds = min_wait_seconds
        self._max_wait_seconds = max_wait_seconds
        self._max_tilt_degrees = max_tilt_degrees
        self._sway_duration_seconds = sway_duration_seconds
        self._rng = rng if rng is not None else random.Random()

        self._time_until_next_sway = self._roll_wait()
        self._is_swaying = False
        self._sway_elapsed_seconds = 0.0
        self._target_tilt_degrees = 0.0

    def _roll_wait(self) -> float:
        return self._rng.uniform(self._min_wait_seconds, self._max_wait_seconds)

    def advance(self, delta_time: float) -> None:
        """Move the sway schedule forward by ``delta_time`` seconds."""
        if self._is_swaying:
            self._sway_elapsed_seconds += delta_time
            if self._sway_elapsed_seconds >= self._sway_duration_seconds:
                self._is_swaying = False
                self._sway_elapsed_seconds = 0.0
                self._time_until_next_sway = self._roll_wait()
        else:
            self._time_until_next_sway -= delta_time
            if self._time_until_next_sway <= 0.0:
                self._is_swaying = True
                self._sway_elapsed_seconds = 0.0
                self._target_tilt_degrees = self._rng.uniform(
                    -self._max_tilt_degrees, self._max_tilt_degrees
                )

    @property
    def is_swaying(self) -> bool:
        """Whether a sway is in progress right now."""
        return self._is_swaying

    @property
    def tilt_degrees(self) -> float:
        """Current rotation in degrees: 0 at rest, easing smoothly up
        to the target tilt and back down to 0 across the sway."""
        if not self._is_swaying:
            return 0.0
        progress = min(self._sway_elapsed_seconds / self._sway_duration_seconds, 1.0)
        # Half-sine ease: rises from 0 to 1 and back to 0 across the
        # sway, so the tilt starts and ends at rest with no snapping.
        ease = math.sin(progress * math.pi)
        return self._target_tilt_degrees * ease
