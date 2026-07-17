"""
desktop_pet.core.app
========================

Composition root for the application. Creates the QApplication,
resolves which sprite to display, wires the GameLoop to the PetWindow,
and runs the Qt event loop.

Sprite resolution: if the user has placed a custom sprite at
``assets/sprites/user_pet.png``, it is used instead of the generated
placeholder. This lets someone drop in their own image with zero code
changes — no config editing required for Phase 2. A proper, declarative
"active pet" system (reading ``config/default_config.json``'s
``pet.active_pet`` key and a full plugin folder) arrives in Phase 8.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from desktop_pet.core.loop import GameLoop
from desktop_pet.core.paths import get_assets_dir
from desktop_pet.ui.pet_window import PetWindow

logger = logging.getLogger("desktop_pet.core.app")


def resolve_sprite_path() -> Path:
    """Prefer a user-supplied sprite over the generated placeholder."""
    sprites_dir = get_assets_dir() / "sprites"
    user_sprite = sprites_dir / "user_pet.png"
    if user_sprite.exists():
        logger.info("Using custom sprite: %s", user_sprite)
        return user_sprite

    placeholder_sprite = sprites_dir / "placeholder_pet.png"
    logger.info("No custom sprite found, using placeholder: %s", placeholder_sprite)
    return placeholder_sprite


class Application:
    """Owns the QApplication, the pet window, and the game loop."""

    def __init__(self, argv: list[str] | None = None) -> None:
        self._qt_app = QApplication(argv if argv is not None else sys.argv)
        self._qt_app.setApplicationName("Desktop Pet")
        self._qt_app.setQuitOnLastWindowClosed(True)

        sprite_path = resolve_sprite_path()
        self._window = PetWindow(sprite_path)

        self._loop = GameLoop(target_fps=60)
        self._loop.subscribe(self._window.advance)

    def run(self) -> int:
        self._window.show()
        self._loop.start()
        logger.info(
            "Desktop Pet window shown at %d FPS. Press Esc (with the window "
            "focused) to quit.",
            self._loop.target_fps,
        )
        return self._qt_app.exec()
