"""Unit tests for desktop_pet.ai.state and desktop_pet.ai.state_machine."""

from __future__ import annotations

import pytest

from desktop_pet.ai.behavior_engine import BehaviorEngine
from desktop_pet.ai.event_bus import EventBus
from desktop_pet.ai.events import Event, EventType
from desktop_pet.ai.state import PetState, State
from desktop_pet.ai.state_machine import (
    DraggedState,
    FollowCursorState,
    HappyState,
    HugState,
    IdleState,
    JumpState,
    LegSwingState,
    ReadState,
    RunState,
    SleepState,
    StateMachine,
    ThrownState,
    WalkState,
    WaveState,
)

ALL_PLACEHOLDER_STATE_CLASSES = [
    IdleState,
    WalkState,
    RunState,
    SleepState,
    ReadState,
    JumpState,
    WaveState,
    HappyState,
    LegSwingState,
    HugState,
    FollowCursorState,
    DraggedState,
    ThrownState,
]


class _RecordingState(State):
    """A test double that records lifecycle calls in order."""

    state_id = PetState.IDLE

    def __init__(self, engine, calls: list[str], state_id: PetState | None = None) -> None:
        if state_id is not None:
            self.state_id = state_id
        super().__init__(engine)
        self._calls = calls

    def enter(self) -> None:
        self._calls.append(f"enter:{self.state_id.value}")

    def update(self, delta_time: float) -> None:
        self._calls.append(f"update:{self.state_id.value}:{delta_time}")

    def exit(self) -> None:
        self._calls.append(f"exit:{self.state_id.value}")


def _make_engine() -> BehaviorEngine:
    return BehaviorEngine(config={"initial_state": "idle"})


class TestStateBaseClass:
    def test_requires_state_id_to_be_set(self) -> None:
        class MissingStateId(State):
            pass

        with pytest.raises(TypeError):
            MissingStateId(engine=None)

    def test_default_lifecycle_methods_are_no_ops(self) -> None:
        state = IdleState(engine=None)
        state.enter()
        state.update(0.5)
        state.exit()  # No exception means success.

    def test_engine_property_returns_constructor_argument(self) -> None:
        sentinel = object()
        state = IdleState(engine=sentinel)
        assert state.engine is sentinel


class TestPlaceholderStates:
    @pytest.mark.parametrize("state_cls", ALL_PLACEHOLDER_STATE_CLASSES)
    def test_each_placeholder_state_is_instantiable_and_inert(self, state_cls) -> None:
        state = state_cls(engine=None)
        state.enter()
        state.update(1 / 60)
        state.exit()

    def test_all_required_states_exist(self) -> None:
        expected_ids = {
            PetState.IDLE,
            PetState.WALK,
            PetState.RUN,
            PetState.SLEEP,
            PetState.READ,
            PetState.JUMP,
            PetState.WAVE,
            PetState.HAPPY,
            PetState.LEG_SWING,
            PetState.HUG,
            PetState.FOLLOW_CURSOR,
            PetState.DRAGGED,
            PetState.THROWN,
        }
        actual_ids = {cls.state_id for cls in ALL_PLACEHOLDER_STATE_CLASSES}
        assert actual_ids == expected_ids


class TestStateMachine:
    def test_starts_with_no_current_state(self) -> None:
        engine = BehaviorEngine.__new__(BehaviorEngine)
        engine._event_bus = EventBus()
        machine = StateMachine(engine)
        assert machine.current_state_id is None

    def test_transition_to_unregistered_state_raises(self) -> None:
        engine = BehaviorEngine.__new__(BehaviorEngine)
        engine._event_bus = EventBus()
        machine = StateMachine(engine)
        with pytest.raises(ValueError):
            machine.transition_to(PetState.WALK)

    def test_registering_duplicate_state_id_raises(self) -> None:
        engine = BehaviorEngine.__new__(BehaviorEngine)
        engine._event_bus = EventBus()
        machine = StateMachine(engine)
        machine.register_state(IdleState(engine))
        with pytest.raises(ValueError):
            machine.register_state(IdleState(engine))

    def test_transition_calls_enter_then_exit_then_enter_in_order(self) -> None:
        engine = BehaviorEngine.__new__(BehaviorEngine)
        engine._event_bus = EventBus()
        machine = StateMachine(engine)
        calls: list[str] = []
        machine.register_state(_RecordingState(engine, calls, PetState.IDLE))
        machine.register_state(_RecordingState(engine, calls, PetState.WALK))

        machine.transition_to(PetState.IDLE)
        machine.transition_to(PetState.WALK)

        assert calls == ["enter:idle", "exit:idle", "enter:walk"]

    def test_transition_to_same_state_is_a_no_op(self) -> None:
        engine = BehaviorEngine.__new__(BehaviorEngine)
        engine._event_bus = EventBus()
        machine = StateMachine(engine)
        calls: list[str] = []
        machine.register_state(_RecordingState(engine, calls, PetState.IDLE))

        machine.transition_to(PetState.IDLE)
        machine.transition_to(PetState.IDLE)

        assert calls == ["enter:idle"]

    def test_update_delegates_to_current_state(self) -> None:
        engine = BehaviorEngine.__new__(BehaviorEngine)
        engine._event_bus = EventBus()
        machine = StateMachine(engine)
        calls: list[str] = []
        machine.register_state(_RecordingState(engine, calls, PetState.IDLE))
        machine.transition_to(PetState.IDLE)

        machine.update(0.016)

        assert calls == ["enter:idle", "update:idle:0.016"]

    def test_update_before_any_transition_is_a_no_op(self) -> None:
        engine = BehaviorEngine.__new__(BehaviorEngine)
        engine._event_bus = EventBus()
        machine = StateMachine(engine)
        machine.update(0.016)  # No exception means success.

    def test_transition_publishes_enter_and_exit_events(self) -> None:
        engine = _make_engine()
        received: list[Event] = []
        engine.event_bus.subscribe(EventType.STATE_ENTERED, received.append)
        engine.event_bus.subscribe(EventType.STATE_EXITED, received.append)

        engine.state_machine.transition_to(PetState.WALK)

        entered = [e for e in received if e.event_type is EventType.STATE_ENTERED]
        exited = [e for e in received if e.event_type is EventType.STATE_EXITED]
        assert entered[-1].payload["state"] is PetState.WALK
        assert exited[-1].payload["state"] is PetState.IDLE