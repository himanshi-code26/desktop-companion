"""
desktop_pet.ui.pet_window
============================

The pet's on-screen window.

Phase 2 scope: a single static sprite shown in a transparent, frameless,
always-on-top window that stays clickable (not click-through), plus a
tiny idle "bob" driven by the real game loop to prove the 60 FPS update
loop is actually running. Sprite-sheet animation, dragging, and cursor
interaction are separate, later phases (3, 5, 6) — this file only owns
the window itself.
"""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QKeyEvent, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QWidget


class PetWindow(QWidget):
    """A borderless, transparent, always-on-top window showing the pet sprite."""

    def __init__(self, sprite_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._elapsed_seconds = 0.0
        self._base_y: int | None = None

        self._configure_window_flags()
        pixmap = self._load_sprite(sprite_path)
        self._sprite_label = self._build_sprite_label(pixmap)
        self._position_window()

    # -- setup -----------------------------------------------------------

    def _configure_window_flags(self) -> None:
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        # Intentionally NOT setting Qt.WA_TransparentForMouseEvents here.
        # Setting it is what makes a window "click-through" (clicks fall
        # through to whatever is behind it). Leaving it unset keeps the
        # pet clickable/focusable, which is what "click-through disabled"
        # requires, and what dragging (a later phase) will depend on.

    def _load_sprite(self, sprite_path: Path) -> QPixmap:
        if not sprite_path.exists():
            raise FileNotFoundError(
                f"Pet sprite not found at {sprite_path}. "
                "Run `python scripts/generate_placeholder_asset.py` or place "
                "your own image there."
            )
        pixmap = QPixmap(str(sprite_path))
        if pixmap.isNull():
            raise ValueError(f"Failed to decode image at {sprite_path}")
        return pixmap

    def _build_sprite_label(self, pixmap: QPixmap) -> QLabel:
        label = QLabel(self)
        label.setPixmap(pixmap)
        label.setScaledContents(True)
        label.setGeometry(0, 0, pixmap.width(), pixmap.height())
        label.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(pixmap.size())
        return label

    def _position_window(self) -> None:
        screen = QGuiApplication.primaryScreen()
        geometry = screen.availableGeometry()
        x = geometry.x() + (geometry.width() - self.width()) // 2
        y = geometry.y() + geometry.height() - self.height() - 40
        self.move(x, y)
        self._base_y = y

    # -- per-frame update --------------------------------------------------

    def advance(self, delta_time: float) -> None:
        """Called once per tick by the GameLoop.

        Phase 2 scope: a small sinusoidal bob, purely to make the 60 FPS
        loop visible on screen and to give later phases (animation,
        physics) a callback to replace. It is real, working motion —
        not a stub — just intentionally simple for this phase.
        """
        self._elapsed_seconds += delta_time
        if self._base_y is None:
            return
        bob_amplitude_px = 6
        bob_speed_radians_per_sec = 2.0
        offset = round(
            bob_amplitude_px * math.sin(self._elapsed_seconds * bob_speed_radians_per_sec)
        )
        self.move(self.x(), self._base_y + offset)

    # -- input ---------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            app = QApplication.instance()
            if app is not None:
                app.quit()
            return
        super().keyPressEvent(event)
