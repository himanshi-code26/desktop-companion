"""
desktop_pet.animation.cursor_awareness
=========================================

Models the pet reacting to how close the cursor is — without ever
moving the pet itself. Three distance zones (near/mid/far) drive a
target "facing" tilt and a small positional "lean", both eased in
smoothly rather than snapped, and interest fades on its own if the
cursor sits still for a while.

Like ``animation.idle``, this class is deliberately Qt-independent —
it only takes plain floats in (a cursor-minus-pet offset in pixels,
and elapsed time) and exposes plain floats out. ``ui.pet_window``
is responsible for reading the real cursor position and applying the
resulting tilt/lean to the rendered sprite.
"""

from __future__ import annotations

import math
import random
from enum import Enum


class CursorZone(Enum):
    """Which of the three distance bands the cursor currently falls in."""

    NEAR = "A"
    """0-180px: very interested — face directly toward the cursor and lean in."""

    MID = "B"
    """180-350px: mildly curious — a small head turn, no lean."""

    FAR = "C"
    """>350px (or bored): ignored — ease back to a neutral, upright idle."""


class CursorAwareness:
    """Reacts to cursor distance/direction without moving the pet.

    Feed it the cursor's offset from the pet's center every frame via
    ``update_cursor``; read back ``tilt_degrees`` and ``lean_offset_px``
    to apply to the sprite's rendering. Both outputs are smoothed with
    an exponential filter (never a hard snap) with a time constant in
    the requested 200-400ms range, so response, however fast the
    target changes, always eases rather than jumps.

    Losing and regaining interest: if the cursor stays within
    ``movement_threshold_px`` of the same spot for a randomly chosen
    10-20 second stretch, interest fades to :attr:`CursorZone.FAR`
    regardless of actual distance, until the cursor moves again — at
    which point normal zone logic (and the same smooth easing) resumes
    immediately.
    """

    ZONE_A_RADIUS_PX: float = 180.0
    ZONE_B_RADIUS_PX: float = 350.0

    def __init__(
        self,
        transition_seconds: float = 0.3,
        zone_a_tilt_degrees: float = 10.0,
        zone_a_lean_px: float = 4.0,
        zone_b_tilt_degrees: float = 4.0,
        min_disinterest_seconds: float = 10.0,
        max_disinterest_seconds: float = 20.0,
        movement_threshold_px: float = 3.0,
        rng: random.Random | None = None,
    ) -> None:
        """
        Args:
            transition_seconds: Exponential smoothing time constant for
                tilt/lean easing. Must sit within the required
                200-400ms window (0.2-0.4).
            zone_a_tilt_degrees: Max facing tilt in Zone A (near).
            zone_a_lean_px: Max positional lean in Zone A (near). Zone B
                never leans, only turns (tilts).
            zone_b_tilt_degrees: Max facing tilt in Zone B (mid).
            min_disinterest_seconds: Shortest possible time the cursor
                can sit still before interest fades.
            max_disinterest_seconds: Longest possible time the cursor
                can sit still before interest fades.
            movement_threshold_px: Cursor movement below this (per
                frame-to-frame comparison) counts as "still".
            rng: Optional ``random.Random`` for deterministic testing.
        """
        if not (0.2 <= transition_seconds <= 0.4):
            raise ValueError("transition_seconds must be within 0.2-0.4 (200-400ms)")
        if min_disinterest_seconds <= 0 or max_disinterest_seconds < min_disinterest_seconds:
            raise ValueError("Require 0 < min_disinterest_seconds <= max_disinterest_seconds")
        if movement_threshold_px < 0:
            raise ValueError("movement_threshold_px must not be negative")

        self._transition_seconds = transition_seconds
        self._zone_a_tilt_degrees = zone_a_tilt_degrees
        self._zone_a_lean_px = zone_a_lean_px
        self._zone_b_tilt_degrees = zone_b_tilt_degrees
        self._min_disinterest_seconds = min_disinterest_seconds
        self._max_disinterest_seconds = max_disinterest_seconds
        self._movement_threshold_px = movement_threshold_px
        self._rng = rng if rng is not None else random.Random()

        self._current_tilt_degrees = 0.0
        self._current_lean_x_px = 0.0
        self._current_lean_y_px = 0.0
        self._target_tilt_degrees = 0.0
        self._target_lean_x_px = 0.0
        self._target_lean_y_px = 0.0

        self._still_seconds = 0.0
        self._disinterest_threshold_seconds = self._roll_disinterest_threshold()
        self._has_lost_interest = False
        self._last_cursor_dx: float | None = None
        self._last_cursor_dy: float | None = None
        self._zone = CursorZone.FAR

    def _roll_disinterest_threshold(self) -> float:
        return self._rng.uniform(self._min_disinterest_seconds, self._max_disinterest_seconds)

    def _update_stillness(self, dx: float, dy: float, delta_time: float) -> None:
        """Track how long the cursor has sat still, and flip
        ``has_lost_interest`` once it's been still long enough."""
        moved = (
            self._last_cursor_dx is None
            or math.hypot(dx - self._last_cursor_dx, dy - self._last_cursor_dy)
            > self._movement_threshold_px
        )
        self._last_cursor_dx = dx
        self._last_cursor_dy = dy

        if moved:
            self._still_seconds = 0.0
            self._has_lost_interest = False
        else:
            self._still_seconds += delta_time
            if self._still_seconds >= self._disinterest_threshold_seconds:
                self._has_lost_interest = True

    def _resolve_zone(self, distance_px: float) -> CursorZone:
        if self._has_lost_interest:
            return CursorZone.FAR
        if distance_px <= self.ZONE_A_RADIUS_PX:
            return CursorZone.NEAR
        if distance_px <= self.ZONE_B_RADIUS_PX:
            return CursorZone.MID
        return CursorZone.FAR

    def _update_targets(self, zone: CursorZone, dx: float, dy: float, distance_px: float) -> None:
        direction_x = dx / distance_px if distance_px > 1e-6 else 0.0
        direction_y = dy / distance_px if distance_px > 1e-6 else 0.0

        if zone is CursorZone.NEAR:
            self._target_tilt_degrees = self._zone_a_tilt_degrees * direction_x
            self._target_lean_x_px = self._zone_a_lean_px * direction_x
            self._target_lean_y_px = self._zone_a_lean_px * direction_y
        elif zone is CursorZone.MID:
            self._target_tilt_degrees = self._zone_b_tilt_degrees * direction_x
            self._target_lean_x_px = 0.0
            self._target_lean_y_px = 0.0
        else:
            self._target_tilt_degrees = 0.0
            self._target_lean_x_px = 0.0
            self._target_lean_y_px = 0.0

    def update_cursor(self, dx: float, dy: float, delta_time: float) -> None:
        """Feed the latest cursor offset and advance by delta_time.

        Args:
            dx: Cursor x minus the pet's center x, in pixels.
            dy: Cursor y minus the pet's center y, in pixels.
            delta_time: Seconds elapsed since the previous call.
        """
        self._update_stillness(dx, dy, delta_time)

        distance_px = math.hypot(dx, dy)
        new_zone = self._resolve_zone(distance_px)
        if new_zone is not CursorZone.FAR and new_zone is not self._zone:
            # Regaining interest (entering NEAR/MID from anywhere) rolls
            # a fresh random disinterest countdown, never a fixed one.
            self._disinterest_threshold_seconds = self._roll_disinterest_threshold()
        self._zone = new_zone

        self._update_targets(new_zone, dx, dy, distance_px)

        # Exponential smoothing: frame-rate independent, and its time
        # constant is chosen within the required 200-400ms window, so
        # the response always eases rather than snapping to target.
        alpha = 1.0 - math.exp(-delta_time / self._transition_seconds)
        diff_tilt = self._target_tilt_degrees - self._current_tilt_degrees
        self._current_tilt_degrees += diff_tilt * alpha
        self._current_lean_x_px += (self._target_lean_x_px - self._current_lean_x_px) * alpha
        self._current_lean_y_px += (self._target_lean_y_px - self._current_lean_y_px) * alpha

    @property
    def tilt_degrees(self) -> float:
        """Current smoothed facing tilt, in degrees."""
        return self._current_tilt_degrees

    @property
    def lean_offset_px(self) -> tuple[float, float]:
        """Current smoothed positional lean, as (x, y) pixels."""
        return (self._current_lean_x_px, self._current_lean_y_px)

    @property
    def zone(self) -> CursorZone:
        """The current distance zone (already accounts for lost interest)."""
        return self._zone

    @property
    def has_lost_interest(self) -> bool:
        """Whether interest has faded due to a still cursor."""
        return self._has_lost_interest
