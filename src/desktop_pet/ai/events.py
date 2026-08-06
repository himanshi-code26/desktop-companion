"""
desktop_pet.ai.events
========================

Event types and the ``Event`` payload dataclass published on the AI
``EventBus``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(Enum):
    """Every kind of event that can be published on the AI event bus.

    This phase only defines the lifecycle events ``BehaviorEngine`` and
    ``StateMachine`` themselves emit. Later AI sessions (mood engine,
    scheduler, memory, cursor AI, etc.) are expected to extend this
    enum as they add new event producers and consumers - the event bus
    itself doesn't need to change to support that.
    """

    STATE_ENTERED = "state_entered"
    """A state's enter() just ran. Payload: {"state": PetState}."""

    STATE_EXITED = "state_exited"
    """A state's exit() just ran. Payload: {"state": PetState}."""

    STATE_CHANGED = "state_changed"
    """A transition completed.
    Payload: {"previous_state": PetState | None, "new_state": PetState}."""

    STATE_TRANSITION_DENIED = "state_transition_denied"
    """A requested transition was rejected (unregistered target state).
    Payload: {"requested_state": Any, "message": str}."""

    CONFIG_LOADED = "config_loaded"
    """AI configuration was resolved (from file or defaults).
    Payload: {"config": dict[str, Any]}."""

    CURSOR_INTEREST_CHANGED = "cursor_interest_changed"
    """Cursor-proximity engagement (see ``behavior.cursor_attention.
    CursorAttention.is_interested``) flipped on or off. Published by
    ``ui.pet_window.PetWindow`` (it's the only thing that knows the
    live cursor and window position) purely as a sensor-data relay -
    it makes no behavioural decision itself. Payload:
    {"is_interested": bool}."""


@dataclass(frozen=True)
class Event:
    """A single, immutable event published on the event bus.

    Attributes:
        event_type: What kind of event this is.
        payload: Arbitrary event-specific data. Kept as a plain dict
            (rather than a per-event-type dataclass) so ``EventBus``
            stays fully generic; each subscriber is expected to know
            the payload shape for the ``EventType`` values it listens
            for (documented above, next to each enum member).
        source: Optional string identifying who published the event
            (e.g. ``"behavior_engine"``), useful for logging/debugging.
    """

    event_type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    source: str | None = None
