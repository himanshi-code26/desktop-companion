"""
desktop_pet.core.config
==========================

Minimal configuration loading for the currently-consumed setting:
``window.size_scale``. The rest of ``default_config.json``'s schema
(physics, behavior, audio, pet selection, etc.) is reserved for the
full customization system in Phase 7 and isn't read yet — this module
stays deliberately small and only grows as later phases actually need
more of it.

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
