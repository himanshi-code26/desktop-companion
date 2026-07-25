"""
desktop_pet.core.app
========================

Composition root for the application. Creates the QApplication,
resolves which sprite to display, wires the GameLoop to the PetWindow,
and runs the Qt event loop.

Sprite resolution: the first PNG (alphabetically) found in
``assets/pets/default/`` is used as the pet's sprite. This lets someone
drop their own sticker into that folder with zero code changes — no
config editing required. If that folder is empty or missing, the
generated placeholder is used instead. A proper, declarative "active
pet" system (reading ``config/default_config.json``'s ``pet.active_pet``
key and a full plugin folder) arrives in Phase 8.

Note that this module only *resolves a path* — it does not validate
that the chosen PNG can actually be decoded. That validation, and the
fallback if decoding fails, is ``PetWindow``'s responsibility (see
``ui.pet_window``), since it already owns image loading and is where a
decode failure is naturally discovered.

Sizing: ``config/default_config.json``'s ``window.size_scale`` is
applied to ``PetWindow.DEFAULT_SPRITE_SIZE`` to get the sprite's actual
target size (1.0 = default size, 2.0 = double, 0.5 = half). Aspect
ratio and smooth scaling are still handled entirely by ``PetWindow`` —
this module just computes *how big*, not *how*.

AI wiring (Phase 6 + Phase 7): this module builds one shared
``ai.EventBus`` and hands it to ``BehaviorEngine``, ``AutonomyController``,
and ``PetWindow`` so they can react to each other's events without
importing one another directly. All the actual *decisions* about what
the pet does live in ``ai.autonomy.AutonomyController`` — this module
only wires the pieces together and ticks them every frame via
``GameLoop``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from desktop_pet.ai import BehaviorEngine, EventBus
from desktop_pet.ai.autonomy import AutonomyController
from desktop_pet.core.config import get_ai_config, get_behavior_config, get_size_scale
from desktop_pet.core.loop import GameLoop
from desktop_pet.core.paths import get_assets_dir, get_placeholder_sprite_path
from desktop_pet.ui.pet_window import DEFAULT_SPRITE_SIZE, PetWindow

logger = logging.getLogger("desktop_pet.core.app")


def _discover_default_pet_sprite() -> Path | None:
    """Return the first PNG (alphabetically) in assets/pets/default/.

    Returns ``None`` if that directory doesn't exist or contains no
    ``.png`` files, so the caller can fall back to the placeholder.
    """
    default_pet_dir = get_assets_dir() / "pets" / "default"
    if not default_pet_dir.is_dir():
        return None

    png_files = sorted(default_pet_dir.glob("*.png"))
    return png_files[0] if png_files else None


def resolve_sprite_path() -> Path:
    """Resolve which PNG to use for the pet sprite.

    Preference order:

    1. The first PNG (alphabetically) found in ``assets/pets/default/``
    2. The generated placeholder sprite
    """
    discovered = _discover_default_pet_sprite()
    if discovered is not None:
        logger.info("Using pet sprite from assets/pets/default/: %s", discovered)
        return discovered

    placeholder_sprite = get_placeholder_sprite_path()
    logger.info(
        "No PNG found in assets/pets/default/, using placeholder: %s",
        placeholder_sprite,
    )
    return placeholder_sprite


def _compute_target_size(size_scale: float) -> int:
    """Apply ``size_scale`` to the sprite's default target size.

    ``size_scale = 1.0`` reproduces ``DEFAULT_SPRITE_SIZE`` exactly;
    ``2.0`` doubles it; ``0.5`` halves it. Rounded to the nearest whole
    pixel, since widget/pixmap dimensions must be integers.
    """
    return round(DEFAULT_SPRITE_SIZE * size_scale)


class Application:
    """Owns the QApplication, the pet window, and the game loop."""

    def __init__(self, argv: list[str] | None = None) -> None:
        self._qt_app = QApplication(argv if argv is not None else sys.argv)
        self._qt_app.setApplicationName("Desktop Pet")
        self._qt_app.setQuitOnLastWindowClosed(True)

        sprite_path = resolve_sprite_path()
        target_size = _compute_target_size(get_size_scale())

        # AI foundation + autonomy (Phase 6 + Phase 7): a single EventBus
        # is shared by the BehaviorEngine, the AutonomyController, and
        # the window, so all three can stay decoupled from one another
        # while still reacting to the same events (state changes,
        # cursor-interest edges). BehaviorEngine only manages *safe*
        # transitions; AutonomyController is what actually decides to
        # start one on its own while idle.
        event_bus = EventBus()
        self._behavior_engine = BehaviorEngine(config=get_ai_config(), event_bus=event_bus)
        self._autonomy = AutonomyController(
            self._behavior_engine, config=get_behavior_config()
        )

        self._window = PetWindow(
            sprite_path,
            fallback_sprite_path=get_placeholder_sprite_path(),
            target_size=target_size,
            event_bus=event_bus,
        )

        self._loop = GameLoop(target_fps=60)
        self._loop.subscribe(self._window.advance)
        self._loop.subscribe(self._behavior_engine.update)
        self._loop.subscribe(self._autonomy.update)

    @property
    def behavior_engine(self) -> BehaviorEngine:
        """The AI subsystem's ``BehaviorEngine``, for tests and later phases."""
        return self._behavior_engine

    @property
    def autonomy(self) -> AutonomyController:
        """The ``AutonomyController`` deciding autonomous behaviours, for tests."""
        return self._autonomy

    def run(self) -> int:
        self._window.show()
        self._loop.start()
        logger.info(
            "Desktop Pet window shown at %d FPS. Press Esc (with the window "
            "focused) to quit.",
            self._loop.target_fps,
        )
        return self._qt_app.exec()