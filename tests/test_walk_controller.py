"""
Unit tests for desktop_pet.physics.walk_controller.WalkController.

All tests are headless (no Qt widgets) — WalkController is deliberately
Qt-free so it can be fully unit-tested without a QApplication.
"""

from __future__ import annotations

import math
import random

import pytest

from desktop_pet.physics.walk_controller import WalkController

# ── helpers ────────────────────────────────────────────────────────────────

def _controller_at(x: float, y: float, speed: float = 100.0) -> WalkController:
    """Return a WalkController whose position is already set to (x, y)."""
    wc = WalkController(x=x, y=y, speed=speed)
    return wc


# ── Construction & basic properties ────────────────────────────────────────


def test_initial_position_stored() -> None:
    wc = WalkController(x=50.0, y=200.0)
    assert wc.x == pytest.approx(50.0)
    assert wc.y == pytest.approx(200.0)
    assert wc.position == pytest.approx((50.0, 200.0))


def test_invalid_speed_raises() -> None:
    with pytest.raises(ValueError):
        WalkController(speed=0.0)
    with pytest.raises(ValueError):
        WalkController(speed=-1.0)


def test_not_walking_before_start() -> None:
    wc = _controller_at(0.0, 0.0)
    assert wc.is_walking is False


def test_update_returns_false_when_not_walking() -> None:
    wc = _controller_at(0.0, 0.0)
    result = wc.update(0.016)
    assert result is False


# ── set_position ────────────────────────────────────────────────────────────


def test_set_position_updates_coordinates() -> None:
    wc = WalkController()
    wc.set_position(300.0, 400.0)
    assert wc.x == pytest.approx(300.0)
    assert wc.y == pytest.approx(400.0)


# ── start_walk ──────────────────────────────────────────────────────────────


def test_start_walk_sets_is_walking() -> None:
    wc = _controller_at(0.0, 0.0)
    wc.start_walk(200.0, 0.0)
    assert wc.is_walking is True


def test_start_walk_too_close_does_not_walk() -> None:
    """A destination < 1 px away is a no-op."""
    wc = _controller_at(100.0, 100.0)
    wc.start_walk(100.0, 100.5)  # 0.5 px — below threshold
    assert wc.is_walking is False


def test_facing_left_when_moving_left() -> None:
    wc = _controller_at(500.0, 0.0)
    wc.start_walk(100.0, 0.0)  # moving left
    assert wc.facing_left is True


def test_facing_right_when_moving_right() -> None:
    wc = _controller_at(100.0, 0.0)
    wc.start_walk(500.0, 0.0)  # moving right
    assert wc.facing_left is False


# ── update / movement ────────────────────────────────────────────────────────


def test_update_moves_toward_destination() -> None:
    """Pet should get closer after each tick."""
    wc = _controller_at(0.0, 0.0, speed=100.0)
    wc.start_walk(300.0, 0.0)

    dist_before = abs(wc.x - 300.0)
    wc.update(0.1)  # should move 10 px
    dist_after = abs(wc.x - 300.0)

    assert dist_after < dist_before
    assert wc.x == pytest.approx(10.0, abs=0.5)


def test_update_does_not_overshoot() -> None:
    """A large time step must not carry the pet past the destination."""
    wc = _controller_at(0.0, 0.0, speed=100.0)
    dest_x, dest_y = 50.0, 0.0
    wc.start_walk(dest_x, dest_y)

    # dt = 10.0 s → would move 1000 px; destination is only 50 px away
    wc.update(10.0)

    assert wc.x == pytest.approx(dest_x, abs=1.0)
    assert wc.y == pytest.approx(dest_y, abs=1.0)
    assert wc.is_walking is False


def test_update_returns_true_while_walking() -> None:
    wc = _controller_at(0.0, 0.0, speed=100.0)
    wc.start_walk(1000.0, 0.0)
    result = wc.update(0.016)
    assert result is True
    assert wc.is_walking is True


def test_update_returns_false_upon_arrival() -> None:
    wc = _controller_at(0.0, 0.0, speed=100.0)
    wc.start_walk(5.0, 0.0)  # very short walk

    # Advance far enough to guarantee arrival.
    result = wc.update(1.0)

    assert result is False
    assert wc.is_walking is False
    assert wc.x == pytest.approx(5.0, abs=1.0)


def test_diagonal_walk_correct_distance_per_step() -> None:
    """Speed should be in screen-pixels/s, not axis-pixels/s."""
    wc = _controller_at(0.0, 0.0, speed=100.0)
    wc.start_walk(300.0, 400.0)  # 500 px diagonal

    wc.update(0.1)  # 10 px step in the direction of travel

    actual_dist = math.hypot(wc.x, wc.y)
    assert actual_dist == pytest.approx(10.0, abs=0.5)


def test_position_stops_exactly_at_destination_after_multiple_steps() -> None:
    """Run a full walk with many small ticks; confirm exact stop."""
    wc = _controller_at(0.0, 0.0, speed=60.0)
    wc.start_walk(120.0, 0.0)  # exactly 2 seconds at 60 px/s

    for _ in range(200):
        if not wc.is_walking:
            break
        wc.update(0.016)

    assert wc.x == pytest.approx(120.0, abs=1.5)
    assert wc.y == pytest.approx(0.0, abs=1.5)
    assert wc.is_walking is False


# ── cancel ───────────────────────────────────────────────────────────────────


def test_cancel_stops_walk_immediately() -> None:
    wc = _controller_at(0.0, 0.0, speed=100.0)
    wc.start_walk(500.0, 0.0)
    assert wc.is_walking is True

    wc.cancel()
    assert wc.is_walking is False

    # Position must not change after cancel.
    x_before = wc.x
    wc.update(1.0)
    assert wc.x == pytest.approx(x_before)


# ── clamp_to_bounds ───────────────────────────────────────────────────────────


def test_clamp_keeps_position_inside_screen() -> None:
    wc = WalkController(x=1000.0, y=800.0)
    # Screen is 800×600 starting at (0,0), pet is 100×100
    wc.clamp_to_bounds(0.0, 0.0, 800.0, 600.0, 100.0, 100.0)
    # Max valid x = 800 - 100 = 700; max valid y = 600 - 100 = 500
    assert wc.x <= 700.0
    assert wc.y <= 500.0


def test_clamp_does_not_move_valid_position() -> None:
    wc = WalkController(x=100.0, y=100.0)
    wc.clamp_to_bounds(0.0, 0.0, 800.0, 600.0, 50.0, 50.0)
    assert wc.x == pytest.approx(100.0)
    assert wc.y == pytest.approx(100.0)


def test_clamp_respects_non_zero_screen_origin() -> None:
    """On a secondary monitor that starts at x=1920."""
    wc = WalkController(x=0.0, y=0.0)  # off-screen to the left
    wc.clamp_to_bounds(1920.0, 0.0, 1280.0, 720.0, 100.0, 100.0)
    assert wc.x >= 1920.0


# ── choose_destination ────────────────────────────────────────────────────────


def test_choose_destination_within_bounds() -> None:
    rng = random.Random(42)
    wc = WalkController(rng=rng)

    for _ in range(50):
        dx, dy = wc.choose_destination(0.0, 0.0, 1920.0, 1080.0, 128.0, 128.0)
        assert 0.0 <= dx <= 1920.0 - 128.0
        assert 0.0 <= dy <= 1080.0 - 128.0


def test_choose_destination_with_non_zero_origin() -> None:
    rng = random.Random(7)
    wc = WalkController(rng=rng)

    for _ in range(20):
        dx, dy = wc.choose_destination(100.0, 50.0, 800.0, 600.0, 64.0, 64.0)
        assert dx >= 100.0
        assert dy >= 50.0
        assert dx <= 100.0 + 800.0 - 64.0
        assert dy <= 50.0 + 600.0 - 64.0


def test_choose_destination_returns_different_positions() -> None:
    """With a real RNG the consecutive destinations should differ most of the time."""
    wc = WalkController()
    positions = {wc.choose_destination(0.0, 0.0, 1920.0, 1080.0, 128.0, 128.0) for _ in range(10)}
    assert len(positions) > 1  # very unlikely to be all identical
