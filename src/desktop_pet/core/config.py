"""
desktop_pet.core.config
==========================

Configuration loading for ``window.size_scale``, the ``ai`` section
(``get_ai_config``), and the ``behavior`` section
(``get_behavior_config``). The rest of ``default_config.json``'s
schema (physics, audio, pet selection, etc.) is reserved for later
phases and isn't read yet — this module only grows as later phases
actually need more of it.

Loading is intentionally forgiving: a missing file, malformed JSON, or
an invalid value never crashes the app - it's logged and a sane
default is used instead, since the pet should still appear even with a
broken config.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from desktop_pet.core.paths import get_config_dir

logger = logging.getLogger("desktop_pet.core.config")

#: Used whenever the configured value is missing, malformed, or invalid.
DEFAULT_SIZE_SCALE: float = 1.0

#: Individual per-key fallbacks for the ``ai`` config section (see
#: ``get_ai_config``). Kept separate from ``DEFAULT_SIZE_SCALE`` above
#: since the AI section has more than one key and is merged key-by-key,
#: not treated as all-or-nothing.
DEFAULT_AI_CONFIG: dict[str, Any] = {
    "initial_state": "idle",
}

#: Individual per-key fallbacks for the ``behavior`` config section
#: (see ``get_behavior_config``). ``personality``, ``idle_frequency``,
#: and ``cursor_interest`` are pre-existing, still-unused keys reserved
#: for a future mood/personality engine; the rest are Phase 7's
#: autonomous-behaviour settings and are the only ones currently read
#: (by ``ai.autonomy.AutonomyController``).
DEFAULT_BEHAVIOR_CONFIG: dict[str, Any] = {
    "personality": "friendly",
    "idle_frequency": 0.5,
    "cursor_interest": 0.6,
    "follow_cursor_timeout_seconds": 20,
    "enabled": True,
    "min_idle_seconds": 15.0,
    "max_idle_seconds": 45.0,
    "sleep_probability": 1.0,
    "read_probability": 1.0,
    "wave_probability": 1.0,
    "happy_probability": 1.0,
    "leg_swing_probability": 1.0,
    "hug_probability": 1.0,
}


def _load_raw_config() -> dict[str, Any]:
    """Load default_config.json as a plain dict.

    Returns an empty dict (not an exception) if the file is missing or
    isn't valid JSON, so callers can apply their own defaults.
    """
    config_path = get_config_dir() / "default_config.json"
    try:
        with config_path.open("r", encoding="utf-8") as config_file:
            return json.load(config_file)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning(
            "Could not load config from %s (%s); using defaults.", config_path, exc
        )
        return {}


def get_size_scale() -> float:
    """Return ``window.size_scale`` from default_config.json.

    Falls back to ``DEFAULT_SIZE_SCALE`` if the config file, the
    ``window`` section, or the ``size_scale`` key is missing, or if the
    value isn't a positive number.
    """
    config = _load_raw_config()
    window_config = config.get("window", {})
    raw_scale = window_config.get("size_scale", DEFAULT_SIZE_SCALE)

    try:
        scale = float(raw_scale)
    except (TypeError, ValueError):
        logger.warning(
            "window.size_scale (%r) is not a number; using default %.1f.",
            raw_scale,
            DEFAULT_SIZE_SCALE,
        )
        return DEFAULT_SIZE_SCALE

    if scale <= 0:
        logger.warning(
            "window.size_scale (%s) must be positive; using default %.1f.",
            scale,
            DEFAULT_SIZE_SCALE,
        )
        return DEFAULT_SIZE_SCALE

    return scale


def get_ai_config() -> dict[str, Any]:
    """Return the ``ai`` section of default_config.json, defaults applied.

    Missing keys fall back to ``DEFAULT_AI_CONFIG``'s values
    individually (a shallow merge), not the whole section at once, so
    a config file that only overrides one AI key doesn't lose the
    built-in defaults for the others. If the ``ai`` section itself is
    missing or isn't a JSON object, the full default is used instead
    and a warning is logged - this never crashes the app, matching
    ``get_size_scale``'s forgiving-by-design approach.
    """
    config = _load_raw_config()
    raw_ai_config = config.get("ai", {})

    if not isinstance(raw_ai_config, dict):
        logger.warning(
            "ai config section (%r) is not an object; using defaults.", raw_ai_config
        )
        raw_ai_config = {}

    resolved = {**DEFAULT_AI_CONFIG, **raw_ai_config}
    logger.info("AI configuration loaded: %s", resolved)
    return resolved


def get_behavior_config() -> dict[str, Any]:
    """Return the ``behavior`` section of default_config.json, defaults applied.

    Missing keys fall back to ``DEFAULT_BEHAVIOR_CONFIG``'s values
    individually (a shallow merge), so overriding just e.g.
    ``sleep_probability`` doesn't lose the defaults for every other
    key. If the ``behavior`` section itself is missing or isn't a JSON
    object, the full default is used instead and a warning is logged -
    consistent with ``get_ai_config``'s forgiving-by-design approach.

    Individual value validation (e.g. that a probability is a
    non-negative number, or that ``min_idle_seconds`` <=
    ``max_idle_seconds``) is deliberately left to the consumer
    (``ai.autonomy.AutonomyController``) rather than done here, the
    same way ``get_ai_config`` leaves ``initial_state`` validation to
    ``BehaviorEngine`` - this function's job is only to resolve *which*
    section of the file to read.
    """
    config = _load_raw_config()
    raw_behavior_config = config.get("behavior", {})

    if not isinstance(raw_behavior_config, dict):
        logger.warning(
            "behavior config section (%r) is not an object; using defaults.",
            raw_behavior_config,
        )
        raw_behavior_config = {}

    resolved = {**DEFAULT_BEHAVIOR_CONFIG, **raw_behavior_config}
    logger.info("Behavior configuration loaded: %s", resolved)
    return resolved