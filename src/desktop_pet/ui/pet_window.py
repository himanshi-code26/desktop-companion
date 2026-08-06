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

AI integration (Phase 7): an optional ``event_bus`` can be supplied so
this window can participate in the autonomous-behaviour system without
containing any of its decision logic. Two things happen if (and only
if) one is given:

- Every frame, this window relays ``CursorAttention.is_interested`` as
  an ``EventType.CURSOR_INTEREST_CHANGED`` event whenever it flips —
  this is a plain sensor-data relay (this window is the only thing
  that knows the live cursor and window position), not a behavioural
  decision. ``ai.autonomy.AutonomyController`` is what decides what to
  do with that signal (interrupting sleep/reading/leg-swing).
- This window tracks the AI's current state via
  ``EventType.STATE_CHANGED`` purely so it can suppress the cursor-tilt
  rotation while an interruptible behaviour is active (see
  ``ai.autonomy.INTERRUPTIBLE_BEHAVIOR_STATES``) — cursor awareness is
  meant to "take over" only once the pet is back in ``IDLE``.
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

from desktop_pet.ai import Event, EventBus, EventType, PetState
from desktop_pet.ai.autonomy import INTERRUPTIBLE_BEHAVIOR_STATES
from desktop_pet.animation import BlinkScheduler, BreathingAnimation, SwayAnimation
from desktop_pet.behavior import CursorAttention
from desktop_pet.core.paths import get_placeholder_sprite_path
from desktop_pet.physics.walk_controller import WalkController

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
        event_bus: EventBus | None = None,
        walk_controller: WalkController | None = None,
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
            event_bus: Optional shared ``ai.EventBus``. If given, this
                window publishes ``CURSOR_INTEREST_CHANGED`` and reacts
                to ``STATE_CHANGED`` as described in the module
                docstring above. If omitted (the default), this window
                behaves exactly as it did before Phase 7 - no AI
                coupling at all.
            walk_controller: Optional ``WalkController``. When given,
                ``advance()`` uses it to determine the window's
                position each frame while ``PetState.WALK`` is active,
                and flips the sprite horizontally when the pet is
                moving left. If ``None``, walk-related behaviour is
                silently skipped and all existing idle behaviour is
                unchanged.
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

        self._event_bus = event_bus
        self._current_ai_state: PetState | None = None
        self._last_published_is_interested: bool | None = None
        if self._event_bus is not None:
            self._event_bus.subscribe(EventType.STATE_CHANGED, self._on_ai_state_changed)

        # Walk integration
        self._walk_controller: WalkController | None = walk_controller

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
        # Synchronise WalkController's internal position to where the
        # window actually landed, so it never starts from (0, 0).
        if self._walk_controller is not None:
            self._walk_controller.set_position(float(x), float(y))

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

        Walk integration: when a ``WalkController`` is present and the
        AI is in ``PetState.WALK``, the window position is driven by
        the walk controller rather than the breathing offset. Breathing
        still ticks internally so it can resume smoothly the moment the
        pet returns to IDLE. The sprite is additionally flipped
        horizontally (``QTransform.scale(-1, 1)``) when the pet is
        moving left.

        If an ``event_bus`` was supplied, this also relays cursor
        interest on/off edges as ``CURSOR_INTEREST_CHANGED`` events,
        and suppresses the cursor-tilt contribution while the AI is in
        an interruptible autonomous behaviour (sleep/read/leg-swing) -
        see the module docstring.
        """
        self._breathing.advance(delta_time)
        self._blink.advance(delta_time)
        self._sway.advance(delta_time)

        is_walking = (
            self._walk_controller is not None
            and self._current_ai_state is PetState.WALK
        )

        if is_walking and self._walk_controller is not None:
            # Movement is handled by WalkController; PetWindow only
            # reads the computed position and applies it.
            wc = self._walk_controller
            still_moving = wc.update(delta_time)
            # Clamp to screen every frame to guarantee the pet never
            # drifts outside the visible region.
            screen = QGuiApplication.primaryScreen()
            geom = screen.availableGeometry()
            wc.clamp_to_bounds(
                float(geom.x()), float(geom.y()),
                float(geom.width()), float(geom.height()),
                float(self._target_size), float(self._target_size),
            )
            new_x = round(wc.x)
            new_y = round(wc.y)
            self.move(new_x, new_y)
            self._base_y = new_y  # keep base_y current for breathing on return
            _ = still_moving  # arrival detection is in AutonomyController
        else:
            # Breathing controls vertical position when not walking.
            if self._base_y is not None:
                offset = round(self._breathing.offset_px)
                self.move(self.x(), self._base_y + offset)

        cursor_pos = self._cursor_position_provider()
        pet_center_x = self.x() + self._target_size / 2
        pet_center_y = self.y() + self._target_size / 2
        self._cursor_attention.advance(
            delta_time, cursor_pos.x(), cursor_pos.y(), pet_center_x, pet_center_y
        )
        self._publish_cursor_interest_if_changed()

        cursor_tilt_degrees = (
            0.0
            if self._current_ai_state in INTERRUPTIBLE_BEHAVIOR_STATES
            else self._cursor_attention.tilt_degrees
        )
        total_rotation_degrees = self._sway.tilt_degrees + cursor_tilt_degrees

        # Build a single compound transform: rotation + blink scale +
        # optional horizontal flip for walking left.
        flip_x = (
            -1.0
            if (is_walking and self._walk_controller is not None
                and self._walk_controller.facing_left)
            else 1.0
        )
        transform = QTransform()
        transform.rotate(total_rotation_degrees)
        transform.scale(flip_x, self._blink.scale_y)
        self._sprite_item.setTransform(transform)

    def _publish_cursor_interest_if_changed(self) -> None:
        """Relay ``CursorAttention.is_interested`` on the shared event bus.

        Publishes only on the rising/falling edge (not every frame),
        and only if an ``event_bus`` was supplied — with none supplied,
        this is a no-op and behavior is unchanged from before Phase 7.
        This is pure sensor-data relay: this window makes no decision
        about *what* an interest change should mean; that's
        ``ai.autonomy.AutonomyController``'s job.
        """
        if self._event_bus is None:
            return
        is_interested = self._cursor_attention.is_interested
        if is_interested == self._last_published_is_interested:
            return
        self._last_published_is_interested = is_interested
        self._event_bus.publish(
            Event(
                EventType.CURSOR_INTEREST_CHANGED,
                {"is_interested": is_interested},
                source="pet_window",
            )
        )

    def _on_ai_state_changed(self, event: Event) -> None:
        """Track the AI's current state.

        Used for two things:
        1. Gate cursor-tilt rendering during interruptible behaviours.
        2. Kick off a walk when transitioning into ``PetState.WALK``:
           pick a destination from the current screen geometry and
           hand it to ``WalkController.start_walk()``. PetWindow is
           the right place to do this because it's the only subsystem
           that owns (and reads) the live screen geometry.
        """
        new_state = event.payload.get("new_state")
        self._current_ai_state = new_state

        if new_state is PetState.WALK and self._walk_controller is not None:
            screen = QGuiApplication.primaryScreen()
            geom = screen.availableGeometry()
            dest_x, dest_y = self._walk_controller.choose_destination(
                float(geom.x()), float(geom.y()),
                float(geom.width()), float(geom.height()),
                float(self._target_size), float(self._target_size),
            )
            self._walk_controller.start_walk(dest_x, dest_y)

        elif new_state is not PetState.WALK and self._walk_controller is not None:
            # Cancel any lingering walk (e.g. if interrupted externally).
            self._walk_controller.cancel()

    # -- input ---------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            app = QApplication.instance()
            if app is not None:
                app.quit()
            return
        super().keyPressEvent(event)
