"""
desktop_pet.ai.state_machine
===============================

The finite state machine that drives the pet's behavior, plus the set
of placeholder ``State`` subclasses available in this phase.

Placeholder states
-------------------
``IdleState``, ``WalkState``, ``RunState``, ``SleepState``,
``ReadState``, ``JumpState``, ``WaveState``, ``FollowCursorState``,
``DraggedState``, and ``ThrownState`` are intentionally empty: they
inherit ``enter()``/``update()``/``exit()`` straight from ``State``
without overriding any of them. They exist now purely so the state
machine has real states to register and safely transition between;
later AI sessions fill in each one's actual behavior (walking/physics,
sleeping, reading, cursor-follow logic, drag/throw interaction, etc.)
without needing to touch this file's FSM plumbing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from desktop_pet.ai.events import Event, EventType
from desktop_pet.ai.state import PetState, State

if TYPE_CHECKING:
    from desktop_pet.ai.behavior_engine import BehaviorEngine

logger = logging.getLogger("desktop_pet.ai.state_machine")


class StateMachine:
    """Owns state registration and performs safe transitions between them.

    "Safe" here means:

    - a transition to an unregistered state is rejected (raises
      ``ValueError``) rather than silently leaving the pet in a broken
      or undefined state;
    - transitioning to the already-active state is a no-op - it never
      re-runs ``exit()``/``enter()`` on the same state;
    - the outgoing state's ``exit()`` always completes before the
      incoming state's ``enter()`` runs, so exactly one state is ever
      "active" at a time.

    This class doesn't decide *when* to transition - that's
    ``BehaviorEngine`` (and, in later sessions, whatever drives it:
    mood, scheduler, cursor signals, physics events, etc.). It only
    guarantees that whatever transition is requested happens safely.
    """

    def __init__(self, engine: BehaviorEngine) -> None:
        """
        Args:
            engine: The owning ``BehaviorEngine``. Used only to publish
                ``STATE_ENTERED``/``STATE_EXITED`` events on its event
                bus, and to construct each registered ``State``.
        """
        self._engine = engine
        self._states: dict[PetState, State] = {}
        self._current: State | None = None

    def register_state(self, state: State) -> None:
        """Register a ``State`` instance, keyed by its ``state_id``.

        Args:
            state: The state instance to register.

        Raises:
            ValueError: if a state is already registered for
                ``state.state_id``.
        """
        if state.state_id in self._states:
            raise ValueError(f"A state is already registered for {state.state_id}")
        self._states[state.state_id] = state
        logger.debug("Registered state %s (%s)", state.state_id, type(state).__name__)

    def has_state(self, state_id: PetState) -> bool:
        """Return whether a state is registered for ``state_id``."""
        return state_id in self._states

    @property
    def current_state_id(self) -> PetState | None:
        """The currently-active state's ``PetState``, or ``None`` before the first transition."""
        return self._current.state_id if self._current is not None else None

    def transition_to(self, state_id: PetState) -> None:
        """Safely switch the active state to ``state_id``.

        Args:
            state_id: The ``PetState`` to transition to. Must already
                be registered via :meth:`register_state`.

        Raises:
            ValueError: if ``state_id`` isn't registered.
        """
        if state_id not in self._states:
            raise ValueError(f"Cannot transition to unregistered state: {state_id}")

        if self._current is not None and self._current.state_id == state_id:
            logger.debug("Ignoring no-op transition to already-active state %s", state_id)
            return

        previous_state_id = self.current_state_id

        if self._current is not None:
            self._current.exit()
            self._engine.event_bus.publish(
                Event(
                    EventType.STATE_EXITED,
                    {"state": previous_state_id},
                    source="state_machine",
                )
            )

        self._current = self._states[state_id]
        self._current.enter()
        self._engine.event_bus.publish(
            Event(EventType.STATE_ENTERED, {"state": state_id}, source="state_machine")
        )

        logger.info("State transition: %s -> %s", previous_state_id, state_id)

    def update(self, delta_time: float) -> None:
        """Advance the currently-active state by ``delta_time`` seconds.

        No-op if no transition has happened yet (``current_state_id``
        is ``None``), so callers don't need to special-case startup.
        """
        if self._current is not None:
            self._current.update(delta_time)


# --- Placeholder states -------------------------------------------------
# None of these implement real behavior yet. See the module docstring
# above for why - and note that adding real behavior to one of these
# later should only ever mean overriding enter()/update()/exit() on the
# relevant class; the class itself, its registration, and its
# transitions all already work today.


class IdleState(State):
    """Placeholder for the pet's resting/default state."""

    state_id = PetState.IDLE


class WalkState(State):
    """Placeholder for ground-level locomotion (Phase 4/6 physics + AI)."""

    state_id = PetState.WALK


class RunState(State):
    """Placeholder for faster ground-level locomotion."""

    state_id = PetState.RUN


class SleepState(State):
    """Placeholder for the pet's sleeping state."""

    state_id = PetState.SLEEP


class ReadState(State):
    """Placeholder for the pet's reading state."""

    state_id = PetState.READ


class JumpState(State):
    """Placeholder for a jump action/animation."""

    state_id = PetState.JUMP


class WaveState(State):
    """Placeholder for a wave/greeting action."""

    state_id = PetState.WAVE


class HappyState(State):
    """Placeholder for a brief autonomous 'happy' expression."""

    state_id = PetState.HAPPY


class LegSwingState(State):
    """Placeholder for an idle leg-swing fidget."""

    state_id = PetState.LEG_SWING


class HugState(State):
    """Placeholder for a brief self-hug/affection gesture."""

    state_id = PetState.HUG


class FollowCursorState(State):
    """Placeholder for actively following the cursor (movement, not just tilt)."""

    state_id = PetState.FOLLOW_CURSOR


class DraggedState(State):
    """Placeholder for while the user is dragging the pet."""

    state_id = PetState.DRAGGED


class ThrownState(State):
    """Placeholder for the pet's in-flight/landing reaction after being thrown."""

    state_id = PetState.THROWN
