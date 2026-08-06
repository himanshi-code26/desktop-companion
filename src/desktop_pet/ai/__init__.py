"""
desktop_pet.ai
================

The pet's AI subsystem.

Phase 6 - Session 1 (AI Foundation) status
-------------------------------------------
This package currently provides only the *architectural foundation* for
future AI features:

- ``state``          : the ``PetState`` enum and the base ``State`` class.
- ``events``          : the ``EventType`` enum and the ``Event`` payload.
- ``event_bus``       : a generic publish/subscribe ``EventBus``.
- ``state_machine``   : the ``StateMachine`` plus placeholder state classes.
- ``behavior_engine``  : ``BehaviorEngine``, the composition root that owns
                        the state machine, event bus, and AI configuration.

No concrete state implements real behavior yet, and nothing in this
package touches physics, cursor logic, animation, audio, or mood/
personality/scheduling - those are later AI sessions. Today, the
BehaviorEngine only manages safe transitions between placeholder
states.

Like the rest of ``desktop_pet``, everything in this package is
Qt-independent (plain Python objects), so it's fully unit-testable
without a ``QApplication`` and can be driven by ``core.loop.GameLoop``
the same way ``ui.pet_window.PetWindow`` already is.
"""

from desktop_pet.ai.behavior_engine import BehaviorEngine
from desktop_pet.ai.event_bus import EventBus
from desktop_pet.ai.events import Event, EventType
from desktop_pet.ai.state import PetState, State
from desktop_pet.ai.state_machine import StateMachine

__all__ = [
    "BehaviorEngine",
    "Event",
    "EventBus",
    "EventType",
    "PetState",
    "State",
    "StateMachine",
]
