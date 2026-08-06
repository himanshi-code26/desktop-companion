"""Unit tests for desktop_pet.ai.autonomy.AutonomyController."""

from __future__ import annotations

import random

from desktop_pet.ai.autonomy import AutonomyController
from desktop_pet.ai.behavior_engine import BehaviorEngine
from desktop_pet.ai.events import Event, EventType
from desktop_pet.ai.state import PetState
from desktop_pet.physics.walk_controller import WalkController


def test_autonomy_idle_range_defaults_to_2_to_5_seconds() -> None:
    engine = BehaviorEngine()
    autonomy = AutonomyController(engine=engine)
    assert autonomy._min_idle_seconds == 2.0
    assert autonomy._max_idle_seconds == 5.0


def test_autonomy_triggers_behavior_after_idle_delay() -> None:
    engine = BehaviorEngine()
    rng = random.Random(42)
    autonomy = AutonomyController(engine=engine, rng=rng)

    assert engine.current_state is PetState.IDLE
    assert autonomy._seconds_until_next_behavior is not None
    assert 2.0 <= autonomy._seconds_until_next_behavior <= 5.0

    # Advance by slightly more than the rolled delay to trigger transition
    delay = autonomy._seconds_until_next_behavior
    autonomy.update(delay + 0.1)

    # BehaviorEngine should have transitioned out of IDLE
    assert engine.current_state is not PetState.IDLE


def test_autonomy_walk_completion_returns_to_idle() -> None:
    engine = BehaviorEngine()
    walk_ctrl = WalkController(speed=100.0)
    rng = random.Random(1)
    autonomy = AutonomyController(engine=engine, rng=rng, walk_controller=walk_ctrl)

    # Force behavior to WALK
    autonomy._begin_behavior(PetState.WALK)
    assert engine.current_state is PetState.WALK

    # Seed walk destination
    walk_ctrl.set_position(0.0, 0.0)
    walk_ctrl.start_walk(10.0, 0.0)
    assert walk_ctrl.is_walking is True

    # Advance walk controller until arrived
    walk_ctrl.update(1.0)
    assert walk_ctrl.is_walking is False

    # Advance autonomy controller to detect arrival
    autonomy.update(0.016)

    # Should have returned to IDLE and rolled a new delay
    assert engine.current_state is PetState.IDLE
    assert autonomy._seconds_until_next_behavior is not None
    assert 2.0 <= autonomy._seconds_until_next_behavior <= 5.0


def test_cursor_interest_interrupts_interruptible_behavior() -> None:
    engine = BehaviorEngine()
    autonomy = AutonomyController(engine=engine)

    # Transition to a non-walk interruptible state (e.g. READ)
    engine.request_transition(PetState.READ)
    autonomy._seconds_remaining_in_behavior = 10.0

    # Publish cursor interest event
    engine.event_bus.publish(
        Event(EventType.CURSOR_INTEREST_CHANGED, {"is_interested": True})
    )

    assert engine.current_state is PetState.IDLE
