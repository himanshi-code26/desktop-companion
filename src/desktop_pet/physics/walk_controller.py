"""
desktop_pet.physics.walk_controller
=====================================

Delta-time–based walk controller for the pet's roaming behaviour.

This module is deliberately **Qt-free**: every coordinate is a plain
``float``; the caller (``ui.pet_window.PetWindow``) is responsible for
actually moving the window on-screen.  Keeping movement logic here and
rendering in ``PetWindow`` keeps the two concerns fully decoupled and
makes the maths 100 % headless-testable.

Responsibilities
-----------------
- Store the current (x, y) position of the pet's top-left corner.
- Accept a call to :meth:`start_walk` with a destination (x, y).
- Each :meth:`update` tick, advance the position toward the destination
  by ``speed * delta_time`` pixels, clamped to the allowed screen
  rectangle, and stop exactly at the destination without overshooting.
- Expose :attr:`is_walking`, :attr:`facing_left`, and
  :attr:`position` for the window to read every frame.
- Pick a random valid destination via :meth:`choose_destination`.
"""

from __future__ import annotations

import logging
import math
import random

logger = logging.getLogger("desktop_pet.physics.walk_controller")

# Minimum distance (px) before we consider the pet "arrived"
_ARRIVAL_THRESHOLD: float = 1.0


class WalkController:
    """Owns the pet's current on-screen position and walk movement.

    Thread safety: all methods run on the Qt main thread (called from
    ``PetWindow.advance`` and ``AutonomyController.update``), so no
    locking is needed.
    """

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        speed: float = 80.0,
        rng: random.Random | None = None,
    ) -> None:
        """
        Args:
            x: Initial top-left x position of the pet window (pixels).
            y: Initial top-left y position of the pet window (pixels).
            speed: Walk speed in pixels per second.
            rng: Optional ``random.Random`` for deterministic testing.
                 Defaults to a fresh, unseeded instance.
        """
        if speed <= 0:
            raise ValueError("speed must be > 0")

        self._x: float = x
        self._y: float = y
        self._speed: float = speed
        self._rng: random.Random = rng if rng is not None else random.Random()

        self._dest_x: float = x
        self._dest_y: float = y
        self._is_walking: bool = False
        self._facing_left: bool = False

    # -- read-only properties ------------------------------------------------

    @property
    def x(self) -> float:
        """Current top-left x of the pet window."""
        return self._x

    @property
    def y(self) -> float:
        """Current top-left y of the pet window."""
        return self._y

    @property
    def position(self) -> tuple[float, float]:
        """Current ``(x, y)`` of the pet's top-left corner."""
        return (self._x, self._y)

    @property
    def is_walking(self) -> bool:
        """``True`` while the pet is actively walking toward a destination."""
        return self._is_walking

    @property
    def facing_left(self) -> bool:
        """``True`` when the pet is moving (or last moved) to the left."""
        return self._facing_left

    @property
    def speed(self) -> float:
        """Walk speed in pixels per second."""
        return self._speed

    # -- mutation ------------------------------------------------------------

    def set_position(self, x: float, y: float) -> None:
        """Teleport the controller to ``(x, y)`` without starting a walk.

        Called by ``PetWindow`` or ``Application`` after the window
        first appears on screen, so the controller's internal position
        matches the window's actual position.
        """
        self._x = float(x)
        self._y = float(y)
        self._dest_x = self._x
        self._dest_y = self._y

    def start_walk(self, dest_x: float, dest_y: float) -> None:
        """Begin walking toward ``(dest_x, dest_y)``.

        If the destination is less than one pixel away, the walk is
        skipped and the pet remains in place (no micro-walk that
        wouldn't be visible).
        """
        dx = dest_x - self._x
        dy = dest_y - self._y
        dist = math.hypot(dx, dy)

        if dist < _ARRIVAL_THRESHOLD:
            logger.debug("start_walk: destination too close (%.1f px), skipping.", dist)
            self._is_walking = False
            return

        self._dest_x = float(dest_x)
        self._dest_y = float(dest_y)
        self._is_walking = True
        # Determine facing direction from horizontal component only.
        self._facing_left = dx < 0
        logger.info(
            "Walk started: (%.1f, %.1f) → (%.1f, %.1f), dist=%.1f px",
            self._x, self._y, self._dest_x, self._dest_y, dist,
        )

    def cancel(self) -> None:
        """Immediately halt the current walk, staying at the current position."""
        if self._is_walking:
            logger.debug("Walk cancelled at (%.1f, %.1f).", self._x, self._y)
        self._is_walking = False

    def update(self, delta_time: float) -> bool:
        """Advance the pet's position by one time step.

        Args:
            delta_time: Seconds elapsed since the previous tick.

        Returns:
            ``True`` while the pet is still walking;
            ``False`` when it has just arrived at the destination
            (or was never walking).
        """
        if not self._is_walking:
            return False

        dx = self._dest_x - self._x
        dy = self._dest_y - self._y
        dist = math.hypot(dx, dy)

        if dist <= _ARRIVAL_THRESHOLD:
            # Snap to destination — prevents infinite sub-pixel drift.
            self._x = self._dest_x
            self._y = self._dest_y
            self._is_walking = False
            logger.info(
                "Walk arrived at (%.1f, %.1f).", self._dest_x, self._dest_y
            )
            return False

        max_step = self._speed * delta_time

        if max_step >= dist:
            # Would overshoot — snap exactly to destination this frame.
            self._x = self._dest_x
            self._y = self._dest_y
            self._is_walking = False
            logger.info(
                "Walk arrived (overshoot-prevented) at (%.1f, %.1f).",
                self._dest_x, self._dest_y,
            )
            return False

        # Normalised direction * step length
        unit_x = dx / dist
        unit_y = dy / dist
        self._x += unit_x * max_step
        self._y += unit_y * max_step
        return True

    def clamp_to_bounds(
        self,
        screen_x: float,
        screen_y: float,
        screen_w: float,
        screen_h: float,
        pet_w: float,
        pet_h: float,
    ) -> None:
        """Clamp the current position so the pet stays on screen.

        Call this after :meth:`update` if you want hard boundary
        enforcement (position never exits the given rectangle).

        Args:
            screen_x: Left edge of the allowed region (usually ``availableGeometry().x()``).
            screen_y: Top edge of the allowed region.
            screen_w: Width of the allowed region.
            screen_h: Height of the allowed region.
            pet_w: Width of the pet window.
            pet_h: Height of the pet window.
        """
        max_x = screen_x + screen_w - pet_w
        max_y = screen_y + screen_h - pet_h
        self._x = max(screen_x, min(self._x, max_x))
        self._y = max(screen_y, min(self._y, max_y))

    def choose_destination(
        self,
        screen_x: float,
        screen_y: float,
        screen_w: float,
        screen_h: float,
        pet_w: float,
        pet_h: float,
    ) -> tuple[float, float]:
        """Pick a uniformly-random valid top-left position on the screen.

        The destination is guaranteed to be fully within the screen
        rectangle (no part of the pet window overhangs any edge).

        Args:
            screen_x: Left edge of the available screen geometry.
            screen_y: Top edge of the available screen geometry.
            screen_w: Width of the available screen geometry.
            screen_h: Height of the available screen geometry.
            pet_w: Width of the pet window.
            pet_h: Height of the pet window.

        Returns:
            ``(dest_x, dest_y)`` as floats.
        """
        max_x = screen_x + screen_w - pet_w
        max_y = screen_y + screen_h - pet_h

        if max_x < screen_x:
            max_x = screen_x  # pet is wider than screen — pin to left
        if max_y < screen_y:
            max_y = screen_y

        dest_x = self._rng.uniform(screen_x, max_x)
        dest_y = self._rng.uniform(screen_y, max_y)
        logger.debug(
            "Destination chosen: (%.1f, %.1f) within screen "
            "(%g, %g, %g, %g), pet (%g×%g).",
            dest_x, dest_y, screen_x, screen_y, screen_w, screen_h, pet_w, pet_h,
        )
        return dest_x, dest_y
