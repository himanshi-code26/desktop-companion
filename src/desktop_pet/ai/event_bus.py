"""
desktop_pet.ai.event_bus
============================

A minimal, generic, synchronous publish/subscribe event bus.

This is what lets AI-related subsystems (the state machine, and later
the mood engine, scheduler, cursor AI, etc.) notify one another without
importing or calling each other directly - matching the loosely-coupled
event-bus architecture already described in ``docs/ARCHITECTURE.md``.
Publishers don't need to know who (if anyone) is listening, and
subscribers don't need to know who published.

This module is deliberately generic: it knows nothing about
``PetState``, the state machine, or any other AI concept. It only
knows how to route :class:`~desktop_pet.ai.events.Event` instances to
callbacks registered for their :class:`~desktop_pet.ai.events.EventType`.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable

from desktop_pet.ai.events import Event, EventType

logger = logging.getLogger("desktop_pet.ai.event_bus")

#: A subscriber receives the published Event and returns nothing.
Subscriber = Callable[[Event], None]


class EventBus:
    """Synchronous, in-process publish/subscribe event bus.

    All dispatch happens on the calling thread, in subscription order,
    inline with :meth:`publish`. This is intentional for this phase:
    the app has no background threads, so synchronous dispatch keeps
    ordering predictable and debugging simple. It can be swapped for a
    queued/async implementation later without changing this class's
    public interface (``subscribe`` / ``unsubscribe`` / ``publish``).
    """

    def __init__(self) -> None:
        self._subscribers: defaultdict[EventType, list[Subscriber]] = defaultdict(list)

    def subscribe(self, event_type: EventType, callback: Subscriber) -> None:
        """Register ``callback`` to be invoked whenever ``event_type`` is published."""
        self._subscribers[event_type].append(callback)
        logger.debug("Subscribed %r to %s", callback, event_type.value)

    def unsubscribe(self, event_type: EventType, callback: Subscriber) -> None:
        """Remove a previously registered subscriber.

        A no-op (not an error) if ``callback`` was never subscribed to
        ``event_type`` - callers shouldn't need to track subscription
        state just to safely unsubscribe during teardown.
        """
        subscribers = self._subscribers.get(event_type)
        if subscribers and callback in subscribers:
            subscribers.remove(callback)
            logger.debug("Unsubscribed %r from %s", callback, event_type.value)

    def publish(self, event: Event) -> None:
        """Publish ``event`` to every subscriber of its type.

        A subscriber that raises is logged (with the traceback) and
        skipped - it never stops the remaining subscribers from being
        notified, and never propagates back to the publisher. A broken
        listener must not be able to break the systems that publish
        events it happens to care about.
        """
        for callback in list(self._subscribers.get(event.event_type, [])):
            try:
                callback(event)
            except Exception:
                logger.exception(
                    "Unhandled error in subscriber %r for event %s",
                    callback,
                    event.event_type.value,
                )
