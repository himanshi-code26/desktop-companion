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

Sprite loading (this update): loading is resilient by design. A
requested sprite is tried first; if it's missing or fails to decode, a
warning is logged and the built-in placeholder is tried instead; if
even that fails, a simple in-memory pixmap is generated so the window
can still open. The image is scaled to fit within a single square
target size (``DEFAULT_SPRITE_SIZE``) while preserving its aspect
ratio and using smooth (non-jagged) resampling, then centered inside
the window — never stretched to fill it.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QKeyEvent, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from desktop_pet.core.paths import get_placeholder_sprite_path

logger = logging.getLogger("desktop_pet.ui.pet_window")

#: Default width/height (in pixels) the pet sprite is scaled to fit
#: within. This is the single source of truth for sprite sizing —
#: change it here to resize the pet everywhere.
DEFAULT_SPRITE_SIZE: int = 128


def _load_pixmap(path: Path) -> QPixmap:
    """Decode a single image file into a QPixmap.

    Raises ``FileNotFoundError`` if the path doesn't exist, or
    ``ValueError`` if the file exists but can't be decoded as an image
    (e.g. it's corrupt or not actually a PNG). Both are plain,
    catchable exceptions so callers can implement fallback behavior.
    """
    if not path.exists():
        raise FileNotFoundError(f"Pet sprite not found at {path}.")
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        raise ValueError(f"Failed to decode image at {path}")
    return pixmap


def _scale_preserving_aspect(pixmap: QPixmap, target_size: int) -> QPixmap:
    """Scale ``pixmap`` to fit within a ``target_size`` x ``target_size`` box.

    Uses ``KeepAspectRatio`` so non-square sprites are never stretched,
    and ``SmoothTransformation`` for high-quality, sharp resampling
    (avoiding the jagged edges a naive/fast resize would produce).
    """
    return pixmap.scaled(
        target_size,
        target_size,
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation,
    )


def _create_emergency_pixmap(target_size: int) -> QPixmap:
    """Build a simple in-memory sprite as an absolute last resort.

    Only used if both the requested sprite and the on-disk placeholder
    fail to load, so the window can still open instead of crashing.
    Drawn entirely in code, so it has no file-system dependency at all.
    """
    pixmap = QPixmap(target_size, target_size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setBrush(QColor(200, 200, 200, 220))
    painter.setPen(QColor(120, 120, 120, 255))
    margin = target_size * 0.1
    painter.drawEllipse(
        QRectF(margin, margin, target_size - 2 * margin, target_size - 2 * margin)
    )
    painter.end()

    return pixmap


class PetWindow(QWidget):
    """A borderless, transparent, always-on-top window showing the pet sprite."""

    def __init__(
        self,
        sprite_path: Path,
        fallback_sprite_path: Path | None = None,
        target_size: int = DEFAULT_SPRITE_SIZE,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._elapsed_seconds = 0.0
        self._base_y: int | None = None
        self._target_size = target_size
        self._fallback_sprite_path = fallback_sprite_path or get_placeholder_sprite_path()

        self._configure_window_flags()
        pixmap = self._load_sprite_with_fallback(sprite_path)
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

    def _load_sprite_with_fallback(self, sprite_path: Path) -> QPixmap:
        """Load ``sprite_path``, falling back to the placeholder, then to
        an in-memory sprite, if needed. This never raises.
        """
        candidates = [sprite_path, self._fallback_sprite_path]
        for index, candidate in enumerate(candidates):
            is_last_candidate = index == len(candidates) - 1
            try:
                raw_pixmap = _load_pixmap(candidate)
            except (FileNotFoundError, ValueError) as exc:
                logger.warning(
                    "Could not load pet sprite from %s (%s).%s",
                    candidate,
                    exc,
                    "" if is_last_candidate else " Falling back to placeholder.",
                )
                continue
            return _scale_preserving_aspect(raw_pixmap, self._target_size)

        logger.warning(
            "All sprite candidates failed to load; using an in-memory "
            "emergency sprite so the pet can still appear."
        )
        return _create_emergency_pixmap(self._target_size)

    def _build_sprite_label(self, pixmap: QPixmap) -> QLabel:
        label = QLabel(self)
        label.setPixmap(pixmap)
        label.setAlignment(Qt.AlignCenter)
        label.setGeometry(0, 0, self._target_size, self._target_size)
        label.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(self._target_size, self._target_size)
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
