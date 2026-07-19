"""
desktop_pet.behavior.cursor_attention
=========================================

Reactive, non-locomotive cursor awareness: the pet notices the cursor
and subtly turns/leans toward it, purely as a rotation applied to the
sprite — it never moves position (no following, no walking, no
dragging). This module is deliberately Qt-independent (plain floats
in, plain floats out) so it's fully unit-testable without a
``QApplication``; ``ui.pet_window.PetWindow`` supplies the actual
cursor and window-center coordinates each frame.

Behavior summary
-----------------
Three concentric distance zones around the pet:

- Zone A (0–180px): "very interested" — a stronger tilt, standing in
  for both "facing" the cursor and "leaning" toward it. There's no
  separate head/body layer to animate independently on a flat sticker,
  so both read as one emphasized lean in the cursor's direction.
- Zone B (180–350px): "mild curiosity" — a smaller tilt ("small head
  turn").
- Zone C (>350px): ignored entirely — tilt eases back to 0.

Engagement (are we close enough to care) is instantaneous and purely
distance-based, per the zone definitions above. Layered on top of
that, a separate stillness timer tracks how long the cursor has sat
within a small radius of where it was when it last moved; if that
exceeds a randomly-rolled 10–20 second window, interest is lost (tilt
eases back to 0) even though the cursor never left the zone — exactly
like a pet's attention wandering. Any further cursor movement
immediately re-engages interest, with a freshly-rolled patience
window. Keeping "am I close enough" and "have I gotten bored" as two
independent pieces of state (rather than one combined check) is what
lets slow, sustained cursor motion still count as "moving" — a naive
frame-to-frame velocity check would misread a slow drift as
stillness.

All transitions are smoothed through frame-rate-independent
exponential interpolation rather than jumping straight to the target,
so the tilt never snaps.
"""

from __future__ import annotations

import math
import random


class CursorAttention:
    """Computes a smoothly-interpolated 'attention tilt' toward the cursor."""

    def __init__(
        self,
        zone_a_radius_px: float = 180.0,
        zone_b_radius_px: float = 350.0,
        zone_a_tilt_degrees: float = 3.0,
        zone_b_tilt_degrees: float = 1.2,
        blend_half_life_seconds: float = 0.12,
        min_disinterest_seconds: float = 10.0,
        max_disinterest_seconds: float = 20.0,
        stillness_threshold_px: float = 4.0,
        rng: random.Random | None = None,
    ) -> None:
        """
        Args:
            zone_a_radius_px: Outer radius (px) of the "very interested"
                zone.
            zone_b_radius_px: Outer radius (px) of the "mild curiosity"
                zone. Must be >= ``zone_a_radius_px``.
            zone_a_tilt_degrees: Target tilt magnitude while in zone A.
            zone_b_tilt_degrees: Target tilt magnitude while in zone B.
            blend_half_life_seconds: Exponential-smoothing half-life
                applied to the tilt every frame; tuned so transitions
                visually settle within roughly 200–400ms without ever
                snapping straight to the target.
            min_disinterest_seconds: Shortest time the cursor can sit
                still (within ``stillness_threshold_px``) before
                interest is lost.
            max_disinterest_seconds: Longest such time.
            stillness_threshold_px: How far the cursor may drift from
                its last "moved" position before that drift counts as
                genuine movement again.
            rng: Optional ``random.Random`` for deterministic testing.
                Defaults to a fresh, unseeded instance.
        """
        if zone_b_radius_px < zone_a_radius_px:
            raise ValueError("zone_b_radius_px must be >= zone_a_radius_px")
        if min_disinterest_seconds <= 0 or max_disinterest_seconds < min_disinterest_seconds:
            raise ValueError(
                "Require 0 < min_disinterest_seconds <= max_disinterest_seconds"
            )
        if blend_half_life_seconds <= 0:
            raise ValueError("blend_half_life_seconds must be positive")

        self._zone_a_radius_px = zone_a_radius_px
        self._zone_b_radius_px = zone_b_radius_px
        self._zone_a_tilt_degrees = zone_a_tilt_degrees
        self._zone_b_tilt_degrees = zone_b_tilt_degrees
        self._blend_half_life_seconds = blend_half_life_seconds
        self._min_disinterest_seconds = min_disinterest_seconds
        self._max_disinterest_seconds = max_disinterest_seconds
        self._stillness_threshold_px = stillness_threshold_px
        self._rng = rng if rng is not None else random.Random()

        self._current_tilt_degrees = 0.0
        self._current_zone = "C"
        self._is_interested = False
        self._is_bored = False
        self._time_still_seconds = 0.0
        self._stillness_reference_pos: tuple[float, float] | None = None
        self._disinterest_deadline_seconds = self._roll_disinterest_deadline()

    def _roll_disinterest_deadline(self) -> float:
        return self._rng.uniform(self._min_disinterest_seconds, self._max_disinterest_seconds)

    def _classify_zone(self, distance_px: float) -> str:
        if distance_px <= self._zone_a_radius_px:
            return "A"
        if distance_px <= self._zone_b_radius_px:
            return "B"
        return "C"

    def _engage(self, cursor_x: float, cursor_y: float) -> None:
        """Reset the stillness/boredom tracking as of a fresh reference point."""
        self._stillness_reference_pos = (cursor_x, cursor_y)
        self._time_still_seconds = 0.0
        self._is_bored = False
        self._disinterest_deadline_seconds = self._roll_disinterest_deadline()

    def advance(
        self,
        delta_time: float,
        cursor_x: float,
        cursor_y: float,
        pet_center_x: float,
        pet_center_y: float,
    ) -> None:
        """Advance the attention model by ``delta_time`` seconds.

        Args:
            delta_time: Seconds elapsed since the last call.
            cursor_x, cursor_y: Current cursor position, in the same
                coordinate space as ``pet_center_x``/``pet_center_y``
                (screen coordinates work fine).
            pet_center_x, pet_center_y: The pet's own current center
                position.
        """
        dx = cursor_x - pet_center_x
        dy = cursor_y - pet_center_y
        distance_px = math.hypot(dx, dy)
        zone = self._classify_zone(distance_px)
        self._current_zone = zone
        in_active_zone = zone != "C"

        if not in_active_zone:
            # Ignored entirely; reset boredom tracking so re-entering a
            # zone later starts with a fresh window of patience.
            self._is_bored = False
            self._time_still_seconds = 0.0
            self._stillness_reference_pos = None
        elif self._stillness_reference_pos is None:
            # Just entered an active zone - start tracking from here.
            self._engage(cursor_x, cursor_y)
        else:
            ref_x, ref_y = self._stillness_reference_pos
            drift_px = math.hypot(cursor_x - ref_x, cursor_y - ref_y)
            if drift_px > self._stillness_threshold_px:
                self._engage(cursor_x, cursor_y)
            else:
                self._time_still_seconds += delta_time
                if self._time_still_seconds >= self._disinterest_deadline_seconds:
                    self._is_bored = True

        self._is_interested = in_active_zone and not self._is_bored

        if self._is_interested:
            magnitude = (
                self._zone_a_tilt_degrees if zone == "A" else self._zone_b_tilt_degrees
            )
            direction = math.copysign(1.0, dx) if dx != 0 else 0.0
            target_tilt_degrees = direction * magnitude
        else:
            target_tilt_degrees = 0.0

        smoothing_factor = 1.0 - 2.0 ** (-delta_time / self._blend_half_life_seconds)
        self._current_tilt_degrees += (
            target_tilt_degrees - self._current_tilt_degrees
        ) * smoothing_factor

    @property
    def tilt_degrees(self) -> float:
        """Current smoothed attention tilt, in degrees."""
        return self._current_tilt_degrees

    @property
    def is_interested(self) -> bool:
        """Whether the pet is currently paying attention to the cursor."""
        return self._is_interested

    @property
    def current_zone(self) -> str:
        """The most recently computed distance zone: ``"A"``, ``"B"``, or ``"C"``."""
        return self._current_zone
