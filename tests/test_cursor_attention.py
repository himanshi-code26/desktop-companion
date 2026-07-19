"""Unit tests for desktop_pet.behavior.cursor_attention.

These tests are Qt-independent - no QApplication or pytest-qt fixtures
needed.
"""

from __future__ import annotations

import random

import pytest

from desktop_pet.behavior.cursor_attention import CursorAttention


def _settle(attention: CursorAttention, cursor_x: float, cursor_y: float, seconds: float = 2.0) -> None:
    """Advance ``attention`` at 60fps for ``seconds`` with a fixed cursor
    position, so any in-flight smoothing has time to converge."""
    steps = int(60 * seconds)
    for _ in range(steps):
        attention.advance(1 / 60, cursor_x, cursor_y, 0.0, 0.0)


class TestConstructionValidation:
    def test_rejects_zone_b_smaller_than_zone_a(self) -> None:
        with pytest.raises(ValueError):
            CursorAttention(zone_a_radius_px=350.0, zone_b_radius_px=180.0)

    def test_rejects_invalid_disinterest_range(self) -> None:
        with pytest.raises(ValueError):
            CursorAttention(min_disinterest_seconds=20.0, max_disinterest_seconds=10.0)

    def test_rejects_non_positive_blend_half_life(self) -> None:
        with pytest.raises(ValueError):
            CursorAttention(blend_half_life_seconds=0.0)


class TestZoneClassification:
    def test_zone_a_within_180px(self) -> None:
        attention = CursorAttention(rng=random.Random(1))
        _settle(attention, cursor_x=100.0, cursor_y=0.0)
        assert attention.current_zone == "A"
        assert attention.is_interested is True

    def test_zone_b_between_180_and_350px(self) -> None:
        attention = CursorAttention(rng=random.Random(2))
        _settle(attention, cursor_x=250.0, cursor_y=0.0)
        assert attention.current_zone == "B"
        assert attention.is_interested is True

    def test_zone_c_beyond_350px_is_ignored(self) -> None:
        attention = CursorAttention(rng=random.Random(3))
        _settle(attention, cursor_x=500.0, cursor_y=0.0)
        assert attention.current_zone == "C"
        assert attention.is_interested is False
        assert attention.tilt_degrees == pytest.approx(0.0, abs=0.05)

    def test_zone_boundaries_are_inclusive_to_the_inner_zone(self) -> None:
        attention = CursorAttention(zone_a_radius_px=180.0, zone_b_radius_px=350.0, rng=random.Random(4))
        _settle(attention, cursor_x=180.0, cursor_y=0.0)
        assert attention.current_zone == "A"


class TestTiltMagnitudeAndDirection:
    def test_zone_a_tilts_toward_cursor_on_the_right(self) -> None:
        attention = CursorAttention(zone_a_tilt_degrees=3.0, rng=random.Random(5))
        _settle(attention, cursor_x=100.0, cursor_y=0.0)
        assert attention.tilt_degrees == pytest.approx(3.0, abs=0.05)

    def test_zone_a_tilts_toward_cursor_on_the_left(self) -> None:
        attention = CursorAttention(zone_a_tilt_degrees=3.0, rng=random.Random(6))
        _settle(attention, cursor_x=-100.0, cursor_y=0.0)
        assert attention.tilt_degrees == pytest.approx(-3.0, abs=0.05)

    def test_zone_b_tilt_is_smaller_than_zone_a(self) -> None:
        attention_a = CursorAttention(rng=random.Random(7))
        _settle(attention_a, cursor_x=100.0, cursor_y=0.0)

        attention_b = CursorAttention(rng=random.Random(8))
        _settle(attention_b, cursor_x=250.0, cursor_y=0.0)

        assert abs(attention_b.tilt_degrees) < abs(attention_a.tilt_degrees)


class TestSmoothInterpolation:
    def test_tilt_never_snaps_instantly_to_target(self) -> None:
        attention = CursorAttention(zone_a_tilt_degrees=3.0, rng=random.Random(9))
        attention.advance(1 / 60, cursor_x=100.0, cursor_y=0.0, pet_center_x=0.0, pet_center_y=0.0)
        # After a single 60fps frame, the tilt should have moved toward
        # the target but not have arrived.
        assert 0.0 < attention.tilt_degrees < 3.0

    def test_tilt_converges_within_a_few_hundred_ms(self) -> None:
        attention = CursorAttention(zone_a_tilt_degrees=3.0, rng=random.Random(10))
        _settle(attention, cursor_x=100.0, cursor_y=0.0, seconds=0.6)
        assert attention.tilt_degrees == pytest.approx(3.0, abs=0.1)


class TestDisinterestAndReengagement:
    def test_loses_interest_after_sustained_stillness(self) -> None:
        attention = CursorAttention(
            min_disinterest_seconds=0.2, max_disinterest_seconds=0.3, rng=random.Random(11)
        )
        # Long enough for the 0.2-0.3s disinterest deadline to pass,
        # plus several smoothing half-lives for the tilt to actually
        # decay back toward 0 afterward.
        _settle(attention, cursor_x=100.0, cursor_y=0.0, seconds=1.0)
        assert attention.is_interested is False
        assert attention.tilt_degrees == pytest.approx(0.0, abs=0.05)

    def test_regains_interest_when_cursor_moves_again(self) -> None:
        attention = CursorAttention(
            min_disinterest_seconds=0.2, max_disinterest_seconds=0.3, rng=random.Random(12)
        )
        _settle(attention, cursor_x=100.0, cursor_y=0.0, seconds=0.5)
        assert attention.is_interested is False

        for i in range(60):  # 1 second of renewed movement
            attention.advance(1 / 60, cursor_x=100.0 + i * 2, cursor_y=0.0, pet_center_x=0.0, pet_center_y=0.0)
        assert attention.is_interested is True

    def test_slow_sustained_drift_does_not_count_as_stillness(self) -> None:
        """A slow but continuous drift away from the reference point
        should keep re-triggering engagement, not be misread as the
        cursor sitting still."""
        attention = CursorAttention(
            min_disinterest_seconds=0.2,
            max_disinterest_seconds=0.3,
            stillness_threshold_px=4.0,
            rng=random.Random(13),
        )
        x = 100.0
        for _ in range(180):  # 3 simulated seconds
            x += 0.5
            attention.advance(1 / 60, cursor_x=x, cursor_y=0.0, pet_center_x=0.0, pet_center_y=0.0)
        assert attention.is_interested is True

    def test_leaving_the_zone_resets_boredom_state(self) -> None:
        """Going quiet (zone C) and coming back to an active zone should
        start a fresh patience window, not resume a stale one."""
        attention = CursorAttention(
            min_disinterest_seconds=0.2, max_disinterest_seconds=0.3, rng=random.Random(14)
        )
        _settle(attention, cursor_x=100.0, cursor_y=0.0, seconds=0.5)
        assert attention.is_interested is False  # bored

        _settle(attention, cursor_x=500.0, cursor_y=0.0, seconds=0.1)  # zone C
        assert attention.current_zone == "C"

        # Re-enter zone A; should be freshly interested, not still bored.
        attention.advance(1 / 60, cursor_x=100.0, cursor_y=0.0, pet_center_x=0.0, pet_center_y=0.0)
        assert attention.is_interested is True
