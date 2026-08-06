"""
desktop_pet.ui.pet_window
============================

The pet's on-screen window.

A transparent, frameless, always-on-top window that stays clickable
(not click-through), showing the pet sprite with continuous idle
animation so it never looks like a frozen image: subtle breathing,
occasional blinks, occasional sway, and now cursor awareness — a
subtle lean/turn toward the cursor based on distance, with no actual
movement. Dragging, walking, and gravity are separate, later phases —
this file only owns the window and its in-place idle/reactive
behavior.

Sprite loading: loading is resilient by design. A requested sprite is
tried first; if it's missing or fails to decode, a warning is logged
and the built-in placeholder is tried instead; if even that fails, a
simple in-memory pixmap is generated so the window can still open. The
image is scaled to fit within a single square target size
(``DEFAULT_SPRITE_SIZE``) while preserving its aspect ratio and using
smooth (non-jagged) resampling, then centered inside the window —
never stretched to fill it.

Rendering: the sprite is drawn via a ``QGraphicsView``/
``QGraphicsPixmapItem`` rather than a plain ``QLabel``. This is what
lets rotation (sway, cursor attention) and vertical scale (blink) be
applied every frame as a cheap transform-matrix update — Qt reuses the
same decoded pixmap and just changes how it's painted — instead of
re-resampling the pixmap 60 times a second, which would be both slower
and prone to visible jitter as the transformed image's bounding box
shifts slightly frame to frame.

Cursor awareness: sway (idle, random) and cursor attention (reactive)
are simply *summed* into one rotation rather than one replacing the
other. Both are individually small and each already eases smoothly
toward its own target (including back to 0), so adding them avoids an
abrupt hand-off discontinuity the moment attention starts or stops —
there's no instant in time where the rendered rotation has to jump
from "whatever sway was doing" to "whatever attention is doing" or
back; it's already a single continuous value.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QCursor,
    QGuiApplication,
    QKeyEvent,
    QPainter,
    QPixmap,
    QTransform,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)

from desktop_pet.animation import BlinkScheduler, BreathingAnimation, SwayAnimation
from desktop_pet.behavior import CursorAttention
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
        cursor_position_provider: Callable[[], QPoint] | None = None,
    ) -> None:
        """
        Args:
            sprite_path: The PNG to display.
            fallback_sprite_path: Used if ``sprite_path`` can't be
                loaded. Defaults to the built-in placeholder.
            target_size: Width/height (px) the sprite is scaled to fit
                within.
            parent: Optional parent widget.
            cursor_position_provider: Zero-argument callable returning
                the current global cursor position as a ``QPoint``.
                Defaults to ``QCursor.pos``. Overridable so tests can
                supply a fixed/fake cursor position instead of
                depending on the real (and, in headless CI, undefined)
                OS cursor.
        """
        super().__init__(parent)

        self._base_y: int | None = None
        self._target_size = target_size
        self._fallback_sprite_path = fallback_sprite_path or get_placeholder_sprite_path()
        self._cursor_position_provider = cursor_position_provider or QCursor.pos

        self._breathing = BreathingAnimation()
        self._blink = BlinkScheduler()
        self._sway = SwayAnimation()
        self._cursor_attention = CursorAttention()

        self._configure_window_flags()
        pixmap = self._load_sprite_with_fallback(sprite_path)
        self._scene, self._view, self._sprite_item = self._build_sprite_view(pixmap)
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

    def _build_sprite_view(
        self, pixmap: QPixmap
    ) -> tuple[QGraphicsScene, QGraphicsView, QGraphicsPixmapItem]:
        """Build the transparent QGraphicsView/Scene/PixmapItem stack.

        The pixmap item's local origin is shifted to its own center
        (via ``setOffset``), so that later applying a rotation/scale
        ``QTransform`` to the item — done every frame in ``advance()``
        — naturally pivots around the sprite's visual center rather
        than its top-left corner.
        """
        scene = QGraphicsScene(0, 0, self._target_size, self._target_size)

        item = QGraphicsPixmapItem(pixmap)
        item.setTransformationMode(Qt.SmoothTransformation)
        item.setOffset(-pixmap.width() / 2, -pixmap.height() / 2)
        item.setPos(self._target_size / 2, self._target_size / 2)
        scene.addItem(item)

        view = QGraphicsView(scene, self)
        view.setGeometry(0, 0, self._target_size, self._target_size)
        view.setFrameShape(QFrame.NoFrame)
        view.setStyleSheet("background: transparent; border: none;")
        view.setAttribute(Qt.WA_TranslucentBackground, True)
        view.setAttribute(Qt.WA_NoSystemBackground, True)
        view.viewport().setAttribute(Qt.WA_TranslucentBackground, True)
        view.viewport().setAutoFillBackground(False)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setRenderHint(QPainter.Antialiasing, True)
        view.setRenderHint(QPainter.SmoothPixmapTransform, True)

        self.resize(self._target_size, self._target_size)
        return scene, view, item

    def _position_window(self) -> None:
        screen = QGuiApplication.primaryScreen()
        geometry = screen.availableGeometry()
        x = geometry.x() + (geometry.width() - self.width()) // 2
        y = geometry.y() + geometry.height() - self.height() - 40
        self.move(x, y)
        self._base_y = y

    # -- per-frame update --------------------------------------------------

    def advance(self, delta_time: float) -> None:
        """Called once per tick by the GameLoop (60 FPS).

        Advances breathing, blink, sway, and cursor attention, then
        applies their current values: breathing moves the whole window
        a few pixels vertically (cursor attention never touches
        position, only rotation, so breathing is never interrupted);
        blink and the combined sway+attention rotation are applied as
        a single transform on the sprite item, pivoting around its
        center thanks to the offset set up in ``_build_sprite_view``.
        """
        self._breathing.advance(delta_time)
        self._blink.advance(delta_time)
        self._sway.advance(delta_time)

        if self._base_y is not None:
            offset = round(self._breathing.offset_px)
            self.move(self.x(), self._base_y + offset)

        cursor_pos = self._cursor_position_provider()
        pet_center_x = self.x() + self._target_size / 2
        pet_center_y = self.y() + self._target_size / 2
        self._cursor_attention.advance(
            delta_time, cursor_pos.x(), cursor_pos.y(), pet_center_x, pet_center_y
        )

        total_rotation_degrees = self._sway.tilt_degrees + self._cursor_attention.tilt_degrees
        transform = QTransform()
        transform.rotate(total_rotation_degrees)
        transform.scale(1.0, self._blink.scale_y)
        self._sprite_item.setTransform(transform)

    # -- input ---------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            app = QApplication.instance()
            if app is not None:
                app.quit()
            return
        super().keyPressEvent(event)
