"""Unit tests for desktop_pet.animation.idle.

These classes are deliberately Qt-independent, so these tests run
without a QApplication and without pytest-qt fixtures.
"""

from __future__ import annotations

import random

import pytest

from desktop_pet.animation.idle import BlinkScheduler, BreathingAnimation, SwayAnimation


class TestBreathingAnimation:
    def test_rejects_negative_amplitude(self) -> None:
        with pytest.raises(ValueError):
            BreathingAnimation(amplitude_px=-1.0)

    def test_rejects_non_positive_period(self) -> None:
        with pytest.raises(ValueError):
            BreathingAnimation(period_seconds=0.0)

    def test_starts_at_zero_offset(self) -> None:
        breathing = BreathingAnimation(amplitude_px=3.0, period_seconds=3.6)
        assert breathing.offset_px == pytest.approx(0.0)

    def test_offset_stays_within_amplitude_over_many_cycles(self) -> None:
        breathing = BreathingAnimation(amplitude_px=3.0, period_seconds=3.6)
        max_abs_offset = 0.0
        for _ in range(60 * 30):  # 30 simulated seconds at 60fps
            breathing.advance(1 / 60)
            max_abs_offset = max(max_abs_offset, abs(breathing.offset_px))
        assert max_abs_offset <= 3.0001

    def test_offset_is_continuous_and_periodic(self) -> None:
        breathing = BreathingAnimation(amplitude_px=4.0, period_seconds=2.0)
        for _ in range(120):  # exactly one full period at 60fps
            breathing.advance(1 / 60)
        # After one full period, we should be back near the start.
        assert breathing.offset_px == pytest.approx(0.0, abs=0.01)


class TestBlinkScheduler:
    def test_rejects_invalid_wait_range(self) -> None:
        with pytest.raises(ValueError):
            BlinkScheduler(min_wait_seconds=10.0, max_wait_seconds=4.0)

    def test_rejects_invalid_duration_range(self) -> None:
        with pytest.raises(ValueError):
            BlinkScheduler(min_duration_seconds=0.2, max_duration_seconds=0.1)

    def test_starts_not_blinking(self) -> None:
        blink = BlinkScheduler(rng=random.Random(1))
        assert blink.is_blinking is False
        assert blink.scale_y == 1.0

    def test_never_blinks_before_min_wait(self) -> None:
        blink = BlinkScheduler(min_wait_seconds=4.0, max_wait_seconds=10.0, rng=random.Random(1))
        # Advance in small steps up to just under the minimum wait.
        elapsed = 0.0
        step = 1 / 60
        while elapsed + step < 4.0:
            blink.advance(step)
            elapsed += step
            assert blink.is_blinking is False

    def test_blink_durations_stay_within_configured_range(self) -> None:
        blink = BlinkScheduler(
            min_wait_seconds=0.05,
            max_wait_seconds=0.1,
            min_duration_seconds=0.12,
            max_duration_seconds=0.18,
            rng=random.Random(42),
        )
        durations: list[float] = []
        was_blinking = False
        current_duration = 0.0
        step = 1 / 60
        for _ in range(60 * 20):  # 20 simulated seconds
            blink.advance(step)
            if blink.is_blinking:
                current_duration += step
            if was_blinking and not blink.is_blinking:
                durations.append(current_duration)
                current_duration = 0.0
            was_blinking = blink.is_blinking

        assert len(durations) > 0
        # Allow one frame-step of slack around the requested 120-180ms.
        assert all(0.12 - step <= d <= 0.18 + step for d in durations)

    def test_scale_y_dips_only_while_blinking(self) -> None:
        blink = BlinkScheduler(
            min_wait_seconds=0.05, max_wait_seconds=0.06, rng=random.Random(3)
        )
        blink.advance(0.1)  # guaranteed past the wait window
        assert blink.is_blinking is True
        assert blink.scale_y < 1.0


class TestSwayAnimation:
    def test_rejects_invalid_wait_range(self) -> None:
        with pytest.raises(ValueError):
            SwayAnimation(min_wait_seconds=20.0, max_wait_seconds=8.0)

    def test_rejects_negative_max_tilt(self) -> None:
        with pytest.raises(ValueError):
            SwayAnimation(max_tilt_degrees=-1.0)

    def test_rejects_non_positive_duration(self) -> None:
        with pytest.raises(ValueError):
            SwayAnimation(sway_duration_seconds=0.0)

    def test_starts_upright(self) -> None:
        sway = SwayAnimation(rng=random.Random(1))
        assert sway.is_swaying is False
        assert sway.tilt_degrees == 0.0

    def test_tilt_never_exceeds_max_degrees(self) -> None:
        sway = SwayAnimation(
            min_wait_seconds=0.1, max_wait_seconds=0.2, max_tilt_degrees=3.0,
            rng=random.Random(5),
        )
        max_abs_tilt = 0.0
        for _ in range(60 * 30):  # 30 simulated seconds
            sway.advance(1 / 60)
            max_abs_tilt = max(max_abs_tilt, abs(sway.tilt_degrees))
        assert max_abs_tilt <= 3.0001

    def test_tilt_eases_back_to_zero_at_end_of_sway(self) -> None:
        sway = SwayAnimation(
            min_wait_seconds=0.05,
            max_wait_seconds=0.06,
            sway_duration_seconds=0.5,
            rng=random.Random(9),
        )
        sway.advance(0.1)  # trigger the sway
        assert sway.is_swaying is True

        sway.advance(0.5)  # run past the full sway duration
        assert sway.is_swaying is False
        assert sway.tilt_degrees == 0.0

    def test_tilt_is_nonzero_mid_sway(self) -> None:
        sway = SwayAnimation(
            min_wait_seconds=0.05,
            max_wait_seconds=0.06,
            sway_duration_seconds=1.0,
            rng=random.Random(9),
        )
        sway.advance(0.1)  # trigger the sway (elapsed resets to 0 here)
        sway.advance(0.3)  # step partway into the ease
        assert sway.is_swaying is True
        assert sway.tilt_degrees != 0.0
