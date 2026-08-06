"""
desktop_pet.ai.state
=======================

The ``PetState`` enum and the base ``State`` class every concrete FSM
state inherits from.

This module is deliberately Qt-independent, matching the convention
already established by ``animation.idle`` and ``behavior.cursor_attention``:
plain Python in, plain Python out, no widgets or windows involved.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Only needed for type hints; importing it for real would create a
    # circular import (behavior_engine -> state_machine -> state).
    from desktop_pet.ai.behavior_engine import BehaviorEngine

logger = logging.getLogger("desktop_pet.ai.state")


class PetState(Enum):
    """Every discrete state the pet's behavior FSM can be in.

    Only the state *identities* are defined in this phase. None of them
    carry behavior yet - each corresponding ``State`` subclass in
    ``state_machine`` is an empty placeholder until a later AI session
    fills it in (walking/physics, sleeping, reading, cursor-follow AI,
    drag/throw interaction, etc.).
    """

    IDLE = "idle"
    WALK = "walk"
    RUN = "run"
    SLEEP = "sleep"
    READ = "read"
    JUMP = "jump"
    WAVE = "wave"
    FOLLOW_CURSOR = "follow_cursor"
    DRAGGED = "dragged"
    THROWN = "thrown"
    HAPPY = "happy"
    LEG_SWING = "leg_swing"
    HUG = "hug"


class State:
    """Base class every concrete FSM state must inherit from.

    Lifecycle contract, enforced by ``StateMachine.transition_to``:

    - ``enter()`` runs exactly once, immediately after the state
      machine switches into this state.
    - ``update(delta_time)`` runs once per tick while this state is
      active (via ``BehaviorEngine.update``, itself driven by
      ``core.loop.GameLoop``).
    - ``exit()`` runs exactly once, immediately before the state
      machine switches to a different state.

    Subclasses must set the class attribute ``state_id`` to the
    ``PetState`` they represent; the state machine uses it as the
    registration key. The placeholder subclasses defined in
    ``state_machine`` implement no behavior yet - they exist purely so
    the FSM has states to register and transition between.
    """

    #: The PetState this class represents. Every subclass must set this
    #: as a class attribute (e.g. ``state_id = PetState.IDLE``).
    state_id: PetState

    def __init__(self, engine: BehaviorEngine) -> None:
        """
        Args:
            engine: The owning ``BehaviorEngine``, given to every state
                so it can, in later sessions, read configuration,
                publish events, or request further transitions. Unused
                by the placeholder states in this phase.
        """
        if not hasattr(self, "state_id"):
            raise TypeError(
                f"{type(self).__name__} must define a class-level 'state_id' "
                "(a PetState value) before it can be instantiated."
            )
        self._engine = engine

    @property
    def engine(self) -> BehaviorEngine:
        """The ``BehaviorEngine`` that owns this state."""
        return self._engine

    def enter(self) -> None:
        """Called once when this state becomes active.

        No-op by default; override in a subclass to add behavior.
        """

    def update(self, delta_time: float) -> None:
        """Called once per tick while this state is active.

        Args:
            delta_time: Seconds elapsed since the previous tick.

        No-op by default; override in a subclass to add behavior.
        """

    def exit(self) -> None:
        """Called once immediately before this state is deactivated.

        No-op by default; override in a subclass to add behavior.
        """

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"{type(self).__name__}(state_id={self.state_id!r})"
