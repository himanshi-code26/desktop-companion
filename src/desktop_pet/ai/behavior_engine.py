"""
desktop_pet.ai.behavior_engine
=================================

``BehaviorEngine`` - the AI subsystem's composition root.

It owns (and only owns, for this phase):

- the current state (via its ``StateMachine``),
- the ``StateMachine`` itself,
- an ``EventBus``,
- the AI configuration section it was constructed with.

For this phase, ``BehaviorEngine`` only manages *safe transitions*
between the placeholder states defined in ``state_machine``. It does
not yet decide *when* to transition - no mood, personality, scheduler,
or cursor logic lives here. ``request_transition`` is the single public
entry point later sessions (and, eventually, physics/cursor/behavior
signals) will call to move the pet between states.
"""

from __future__ import annotations

import logging
from typing import Any

from desktop_pet.ai.event_bus import EventBus
from desktop_pet.ai.events import Event, EventType
from desktop_pet.ai.state import PetState
from desktop_pet.ai.state_machine import (
    DraggedState,
    FollowCursorState,
    IdleState,
    JumpState,
    ReadState,
    RunState,
    SleepState,
    StateMachine,
    ThrownState,
    WalkState,
    WaveState,
)

logger = logging.getLogger("desktop_pet.ai.behavior_engine")

#: Used whenever configuration doesn't specify a valid initial state.
DEFAULT_INITIAL_STATE: PetState = PetState.IDLE

#: Every placeholder state class this phase ships with, keyed by the
#: PetState it represents. BehaviorEngine registers one instance of
#: each with its StateMachine at construction time, so the FSM always
#: has somewhere valid to be and something valid to transition to.
_PLACEHOLDER_STATE_CLASSES = {
    PetState.IDLE: IdleState,
    PetState.WALK: WalkState,
    PetState.RUN: RunState,
    PetState.SLEEP: SleepState,
    PetState.READ: ReadState,
    PetState.JUMP: JumpState,
    PetState.WAVE: WaveState,
    PetState.FOLLOW_CURSOR: FollowCursorState,
    PetState.DRAGGED: DraggedState,
    PetState.THROWN: ThrownState,
}


class BehaviorEngine:
    """Owns the AI subsystem's current state, state machine, event bus, and config."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """
        Args:
            config: The ``ai`` section of the app configuration (see
                ``core.config.get_ai_config``). Defaults to an empty
                dict, in which case every setting falls back to its
                built-in default - the engine never fails to start
                because configuration is missing or incomplete.
            event_bus: Optional ``EventBus`` to use instead of creating
                a new one. Mainly useful for tests, or for later
                sessions that want the AI subsystem to share a bus with
                something else.
        """
        self._config = config if config is not None else {}
        self._event_bus = event_bus if event_bus is not None else EventBus()
        self._state_machine = StateMachine(self)

        for state_cls in _PLACEHOLDER_STATE_CLASSES.values():
            self._state_machine.register_state(state_cls(self))

        self._event_bus.publish(
            Event(EventType.CONFIG_LOADED, {"config": dict(self._config)}, source="behavior_engine")
        )

        initial_state_id = self._resolve_initial_state()
        self.request_transition(initial_state_id)

    # -- configuration -----------------------------------------------------

    def _resolve_initial_state(self) -> PetState:
        """Read ``initial_state`` from config, falling back safely to IDLE."""
        raw_value = self._config.get("initial_state", DEFAULT_INITIAL_STATE.value)
        try:
            return PetState(raw_value)
        except ValueError:
            logger.warning(
                "Configured ai.initial_state %r is not a valid PetState; using %s.",
                raw_value,
                DEFAULT_INITIAL_STATE.value,
            )
            return DEFAULT_INITIAL_STATE

    # -- public API ----------------------------------------------------------

    @property
    def event_bus(self) -> EventBus:
        """The ``EventBus`` shared by the state machine and this engine."""
        return self._event_bus

    @property
    def state_machine(self) -> StateMachine:
        """The underlying ``StateMachine``."""
        return self._state_machine

    @property
    def current_state(self) -> PetState | None:
        """The currently-active ``PetState``, or ``None`` if not yet started."""
        return self._state_machine.current_state_id

    def request_transition(self, state_id: PetState) -> None:
        """Request a transition to ``state_id``.

        On success, publishes ``EventType.STATE_CHANGED`` with the
        previous and new state. If ``state_id`` isn't registered, the
        rejection is logged and ``EventType.STATE_TRANSITION_DENIED``
        is published instead of raising - a bad transition request from
        an upstream system (or a future AI feature) must never crash
        the app.

        Args:
            state_id: The ``PetState`` to transition to.
        """
        previous_state_id = self.current_state

        try:
            self._state_machine.transition_to(state_id)
        except ValueError as exc:
            logger.error("Rejected transition request to %s: %s", state_id, exc)
            self._event_bus.publish(
                Event(
                    EventType.STATE_TRANSITION_DENIED,
                    {"requested_state": state_id, "message": str(exc)},
                    source="behavior_engine",
                )
            )
            return

        if previous_state_id != state_id:
            self._event_bus.publish(
                Event(
                    EventType.STATE_CHANGED,
                    {"previous_state": previous_state_id, "new_state": state_id},
                    source="behavior_engine",
                )
            )

    def update(self, delta_time: float) -> None:
        """Advance the active state by ``delta_time`` seconds.

        Intended to be subscribed directly to ``core.loop.GameLoop``,
        the same way ``ui.pet_window.PetWindow.advance`` already is.

        Args:
            delta_time: Seconds elapsed since the previous tick.
        """
        self._state_machine.update(delta_time)
