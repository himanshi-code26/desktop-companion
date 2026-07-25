"""
desktop_pet.ai.autonomy
==========================

``AutonomyController`` - decides, on its own, what the pet should do
next while idle, and requests those transitions through
``BehaviorEngine``.

Phase 6 built ``BehaviorEngine``/``StateMachine`` so that a transition
can happen *safely*, but nothing ever decided to start one - every
transition in the Phase 6 tests was requested explicitly. This module
is the first thing that initiates transitions on its own: the
autonomous half of the state machine described in Phase 7.

Design
------
- Every autonomous behaviour (a non-idle ``PetState`` the pet can
  spend time in) has a probability weight and a ``[min, max]``
  duration range, held in a :class:`BehaviorProfile`.
- While the engine is ``IDLE``, a randomly-rolled "next behaviour"
  delay counts down every tick (``update(delta_time)``). When it
  reaches zero, one behaviour is chosen by weighted random selection
  and the engine transitions into it for a freshly-rolled random
  duration.
- When that duration elapses, the engine transitions back to
  ``IDLE``, which immediately rolls a new idle delay - the cycle
  repeats indefinitely, with everything re-randomized each time so
  the timing never feels mechanical.
- If the cursor comes close enough to interest
  ``behavior.cursor_attention.CursorAttention`` while an
  *interruptible* behaviour (sleep, read, leg swing, by default) is
  active, the behaviour is cut short and the engine returns to
  ``IDLE`` immediately, letting cursor awareness take over. This
  controller never reads cursor/window position itself - it only
  reacts to ``EventType.CURSOR_INTEREST_CHANGED``, published by
  ``ui.pet_window.PetWindow``.

Nothing here touches Qt, animation, or rendering - it only calls
``BehaviorEngine.request_transition`` and reads
``BehaviorEngine.current_state``, exactly like any other consumer of
that public API. It's driven by delta-time ticks (meant to be
subscribed to the same ``GameLoop`` as everything else), never a
polling loop or a timer of its own.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Any

from desktop_pet.ai.behavior_engine import BehaviorEngine
from desktop_pet.ai.events import Event, EventType
from desktop_pet.ai.state import PetState

logger = logging.getLogger("desktop_pet.ai.autonomy")


@dataclass(frozen=True)
class BehaviorProfile:
    """How likely an autonomous behaviour is to be picked, and how long it lasts.

    Attributes:
        weight: Relative probability weight used in weighted-random
            selection (see :meth:`AutonomyController._choose_behavior`).
            A weight of 0 means the behaviour is never chosen.
        min_duration_seconds: Shortest this behaviour may last once
            chosen.
        max_duration_seconds: Longest this behaviour may last.
        interruptible: Whether nearby cursor interest cuts this
            behaviour short and returns the pet to ``IDLE``.
    """

    weight: float
    min_duration_seconds: float
    max_duration_seconds: float
    interruptible: bool = False

    def __post_init__(self) -> None:
        if self.weight < 0:
            raise ValueError("weight must be >= 0")
        if self.min_duration_seconds <= 0 or self.max_duration_seconds < self.min_duration_seconds:
            raise ValueError(
                "require 0 < min_duration_seconds <= max_duration_seconds"
            )


#: Built-in fallback profile for every autonomous behaviour. Duration
#: ranges match the Phase 7 spec's examples; weights are 1.0 (equal
#: chance) unless overridden by ``core.config.get_behavior_config``.
DEFAULT_BEHAVIOR_PROFILES: dict[PetState, BehaviorProfile] = {
    PetState.SLEEP: BehaviorProfile(
        weight=1.0, min_duration_seconds=30.0, max_duration_seconds=90.0, interruptible=True
    ),
    PetState.READ: BehaviorProfile(
        weight=1.0, min_duration_seconds=15.0, max_duration_seconds=40.0, interruptible=True
    ),
    PetState.WAVE: BehaviorProfile(
        weight=1.0, min_duration_seconds=2.0, max_duration_seconds=4.0, interruptible=False
    ),
    PetState.HAPPY: BehaviorProfile(
        weight=1.0, min_duration_seconds=3.0, max_duration_seconds=5.0, interruptible=False
    ),
    PetState.LEG_SWING: BehaviorProfile(
        weight=1.0, min_duration_seconds=10.0, max_duration_seconds=20.0, interruptible=True
    ),
    PetState.HUG: BehaviorProfile(
        weight=1.0, min_duration_seconds=4.0, max_duration_seconds=8.0, interruptible=False
    ),
}

#: States whose behaviour is cut short (back to IDLE) the moment the
#: cursor becomes interesting. Derived once from the defaults above -
#: interruptibility isn't user-configurable in this phase, only the
#: probability weights are (see ``_WEIGHT_CONFIG_KEYS`` below) - so
#: this is a plain module-level constant rather than something
#: resolved per ``AutonomyController`` instance. Exposed publicly so
#: ``ui.pet_window.PetWindow`` can suppress cursor-reactive rendering
#: during these states without duplicating this list.
INTERRUPTIBLE_BEHAVIOR_STATES: frozenset[PetState] = frozenset(
    state_id for state_id, profile in DEFAULT_BEHAVIOR_PROFILES.items() if profile.interruptible
)

#: Config keys read from the ``behavior`` config section for each
#: PetState's probability *weight* (see
#: ``core.config.get_behavior_config``). Only weights are
#: configurable in this phase; duration ranges use the built-in
#: defaults above.
_WEIGHT_CONFIG_KEYS: dict[PetState, str] = {
    PetState.SLEEP: "sleep_probability",
    PetState.READ: "read_probability",
    PetState.WAVE: "wave_probability",
    PetState.HAPPY: "happy_probability",
    PetState.LEG_SWING: "leg_swing_probability",
    PetState.HUG: "hug_probability",
}

DEFAULT_MIN_IDLE_SECONDS: float = 15.0
DEFAULT_MAX_IDLE_SECONDS: float = 45.0


class AutonomyController:
    """Chooses and times the pet's autonomous idle behaviours."""

    def __init__(
        self,
        engine: BehaviorEngine,
        config: dict[str, Any] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        """
        Args:
            engine: The ``BehaviorEngine`` to request transitions on.
                Must already be constructed (its initial state is read
                immediately, in case it's already ``IDLE``).
            config: The ``behavior`` section of the app configuration
                (see ``core.config.get_behavior_config``). Every value
                falls back to a built-in default if missing, so this
                controller never fails to start because configuration
                is incomplete.
            rng: Optional ``random.Random`` for deterministic testing.
                Defaults to a fresh, unseeded instance.
        """
        self._engine = engine
        self._config = config if config is not None else {}
        self._rng = rng if rng is not None else random.Random()

        self._enabled = bool(self._config.get("enabled", True))
        self._min_idle_seconds, self._max_idle_seconds = self._resolve_idle_range()
        self._profiles = self._resolve_profiles()

        self._seconds_until_next_behavior: float | None = None
        self._seconds_remaining_in_behavior: float | None = None

        self._engine.event_bus.subscribe(EventType.STATE_ENTERED, self._on_state_entered)
        self._engine.event_bus.subscribe(
            EventType.CURSOR_INTEREST_CHANGED, self._on_cursor_interest_changed
        )

        # The engine may already be IDLE by the time this controller is
        # constructed (its own STATE_ENTERED for the initial state was
        # published before we could subscribe to it), so roll the
        # first delay explicitly instead of only ever doing it from
        # the event handler.
        if self._enabled and self._engine.current_state is PetState.IDLE:
            self._roll_next_idle_delay()

    # -- configuration resolution ------------------------------------------

    def _resolve_idle_range(self) -> tuple[float, float]:
        min_seconds = self._config.get("min_idle_seconds", DEFAULT_MIN_IDLE_SECONDS)
        max_seconds = self._config.get("max_idle_seconds", DEFAULT_MAX_IDLE_SECONDS)
        try:
            min_seconds = float(min_seconds)
            max_seconds = float(max_seconds)
            if min_seconds <= 0 or max_seconds < min_seconds:
                raise ValueError
        except (TypeError, ValueError):
            logger.warning(
                "Invalid behavior idle range (%r, %r); using defaults (%s, %s).",
                min_seconds,
                max_seconds,
                DEFAULT_MIN_IDLE_SECONDS,
                DEFAULT_MAX_IDLE_SECONDS,
            )
            return DEFAULT_MIN_IDLE_SECONDS, DEFAULT_MAX_IDLE_SECONDS
        return min_seconds, max_seconds

    def _resolve_profiles(self) -> dict[PetState, BehaviorProfile]:
        """Merge configured probability weights into the default profiles."""
        resolved: dict[PetState, BehaviorProfile] = {}
        for state_id, default_profile in DEFAULT_BEHAVIOR_PROFILES.items():
            config_key = _WEIGHT_CONFIG_KEYS[state_id]
            raw_weight = self._config.get(config_key, default_profile.weight)
            try:
                weight = float(raw_weight)
                if weight < 0:
                    raise ValueError
            except (TypeError, ValueError):
                logger.warning(
                    "behavior.%s (%r) is invalid; using default weight %.2f.",
                    config_key,
                    raw_weight,
                    default_profile.weight,
                )
                weight = default_profile.weight
            resolved[state_id] = BehaviorProfile(
                weight=weight,
                min_duration_seconds=default_profile.min_duration_seconds,
                max_duration_seconds=default_profile.max_duration_seconds,
                interruptible=default_profile.interruptible,
            )
        return resolved

    # -- scheduling ----------------------------------------------------------

    def _roll_next_idle_delay(self) -> None:
        self._seconds_until_next_behavior = self._rng.uniform(
            self._min_idle_seconds, self._max_idle_seconds
        )
        logger.debug("Next autonomous behaviour in %.1fs.", self._seconds_until_next_behavior)

    def _choose_behavior(self) -> PetState | None:
        """Weighted-random pick among behaviours with a positive weight.

        Returns ``None`` if every configured weight is 0 (nothing to
        pick), in which case the caller simply stays idle.
        """
        choices = [
            (state_id, profile.weight)
            for state_id, profile in self._profiles.items()
            if profile.weight > 0
        ]
        if not choices:
            return None

        total_weight = sum(weight for _, weight in choices)
        roll = self._rng.uniform(0, total_weight)
        cumulative = 0.0
        for state_id, weight in choices:
            cumulative += weight
            if roll <= cumulative:
                return state_id
        return choices[-1][0]  # pragma: no cover - float-rounding safety net

    def _begin_behavior(self, state_id: PetState) -> None:
        profile = self._profiles[state_id]
        duration = self._rng.uniform(profile.min_duration_seconds, profile.max_duration_seconds)
        self._seconds_remaining_in_behavior = duration
        logger.info("Starting autonomous behaviour %s for %.1fs.", state_id, duration)
        self._engine.request_transition(state_id)

    # -- event handlers --------------------------------------------------------

    def _on_state_entered(self, event: Event) -> None:
        """Whenever IDLE is (re-)entered, roll a fresh delay for the next behaviour."""
        if event.payload.get("state") is not PetState.IDLE:
            return
        self._seconds_remaining_in_behavior = None
        if self._enabled:
            self._roll_next_idle_delay()

    def _on_cursor_interest_changed(self, event: Event) -> None:
        """Cut an interruptible behaviour short the moment the cursor engages."""
        if not event.payload.get("is_interested"):
            return
        if self._engine.current_state in INTERRUPTIBLE_BEHAVIOR_STATES:
            logger.info(
                "Cursor came close during %s; interrupting back to idle.",
                self._engine.current_state,
            )
            self._seconds_remaining_in_behavior = None
            self._engine.request_transition(PetState.IDLE)

    # -- tick ------------------------------------------------------------------

    def update(self, delta_time: float) -> None:
        """Advance behaviour scheduling by ``delta_time`` seconds.

        Intended to be subscribed directly to ``core.loop.GameLoop``,
        the same way ``BehaviorEngine.update`` already is. Purely
        delta-time driven - no polling, no background timer.
        """
        if not self._enabled:
            return

        if self._engine.current_state is PetState.IDLE:
            if self._seconds_until_next_behavior is None:
                self._roll_next_idle_delay()
                return
            self._seconds_until_next_behavior -= delta_time
            if self._seconds_until_next_behavior <= 0:
                self._seconds_until_next_behavior = None
                chosen = self._choose_behavior()
                if chosen is not None:
                    self._begin_behavior(chosen)
        elif self._seconds_remaining_in_behavior is not None:
            self._seconds_remaining_in_behavior -= delta_time
            if self._seconds_remaining_in_behavior <= 0:
                self._seconds_remaining_in_behavior = None
                self._engine.request_transition(PetState.IDLE)