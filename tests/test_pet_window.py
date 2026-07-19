"""Unit tests for desktop_pet.ui.pet_window.PetWindow.

Run with QT_QPA_PLATFORM=offscreen in headless environments (CI already
sets this — see .github/workflows/ci.yml).
"""

from __future__ import annotations

import logging

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent

from desktop_pet.core.paths import get_assets_dir
from desktop_pet.ui.pet_window import DEFAULT_SPRITE_SIZE, PetWindow


@pytest.fixture
def sprite_path():
    return get_assets_dir() / "sprites" / "placeholder_pet.png"


def _write_test_png(path, width: int, height: int, fill_argb: tuple[int, int, int, int]) -> None:
    """Write a solid-color PNG of the given size and RGBA fill to disk."""
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(QColor(*fill_argb))
    assert image.save(str(path), "PNG")


def test_missing_primary_sprite_falls_back_to_placeholder(qtbot, tmp_path) -> None:
    """Requirement: a missing sprite must never crash the app - it should
    fall back to the built-in placeholder instead."""
    window = PetWindow(tmp_path / "does_not_exist.png")
    qtbot.addWidget(window)

    pixmap = window._sprite_item.pixmap()
    assert pixmap is not None
    assert not pixmap.isNull()


def test_window_is_frameless_and_always_on_top(qtbot, sprite_path) -> None:
    window = PetWindow(sprite_path)
    qtbot.addWidget(window)

    flags = window.windowFlags()
    assert flags & Qt.FramelessWindowHint
    assert flags & Qt.WindowStaysOnTopHint


def test_window_is_not_click_through(qtbot, sprite_path) -> None:
    window = PetWindow(sprite_path)
    qtbot.addWidget(window)

    # Click-through is achieved via WA_TransparentForMouseEvents.
    # It must be OFF for "click-through disabled".
    assert window.testAttribute(Qt.WA_TransparentForMouseEvents) is False


def test_window_has_translucent_background(qtbot, sprite_path) -> None:
    window = PetWindow(sprite_path)
    qtbot.addWidget(window)
    assert window.testAttribute(Qt.WA_TranslucentBackground) is True


def test_sprite_view_is_also_translucent(qtbot, sprite_path) -> None:
    """The sprite is now rendered via an internal QGraphicsView, which
    needs its own translucency attributes - the top-level window being
    translucent alone isn't enough."""
    window = PetWindow(sprite_path)
    qtbot.addWidget(window)

    assert window._view.testAttribute(Qt.WA_TranslucentBackground) is True
    assert window._view.viewport().testAttribute(Qt.WA_TranslucentBackground) is True
    assert window._view.viewport().autoFillBackground() is False


def test_window_size_matches_configured_target_size(qtbot, sprite_path) -> None:
    """Requirement: the window resizes itself to match the sprite size,
    i.e. the configured target size (128x128 by default)."""
    window = PetWindow(sprite_path)
    qtbot.addWidget(window)
    assert window.width() == DEFAULT_SPRITE_SIZE
    assert window.height() == DEFAULT_SPRITE_SIZE


def test_custom_target_size_resizes_window(qtbot, sprite_path) -> None:
    """Requirement: the default size must be configurable from one place."""
    window = PetWindow(sprite_path, target_size=64)
    qtbot.addWidget(window)
    assert window.width() == 64
    assert window.height() == 64


def test_escape_key_quits_application(qtbot, sprite_path, qapp) -> None:
    window = PetWindow(sprite_path)
    qtbot.addWidget(window)

    quit_calls: list[bool] = []
    qapp.quit = lambda: quit_calls.append(True)  # type: ignore[method-assign]

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
    window.keyPressEvent(event)

    assert quit_calls == [True]


def test_advance_moves_window_within_breathing_amplitude(qtbot, sprite_path) -> None:
    """Requirement: breathing is a small (2-4px) vertical movement."""
    window = PetWindow(sprite_path)
    qtbot.addWidget(window)
    base_y = window._base_y

    max_deviation = 0.0
    for _ in range(240):  # a couple of full breathing cycles at 60fps
        window.advance(1 / 60)
        max_deviation = max(max_deviation, abs(window.y() - base_y))

    assert max_deviation <= 4.0


# -- idle animation wiring -------------------------------------------------


def test_blink_squashes_sprite_item_transform(qtbot, sprite_path) -> None:
    """A single large advance() step is guaranteed to land inside a
    blink (max wait is 10s), so this is a fast, deterministic way to
    confirm blinking actually reaches the rendered sprite item."""
    window = PetWindow(sprite_path)
    qtbot.addWidget(window)

    window.advance(11.0)  # exceeds the 4-10s max blink wait

    assert window._blink.is_blinking is True
    transform = window._sprite_item.transform()
    assert transform.m22() == pytest.approx(window._blink.scale_y)
    assert transform.m22() < 1.0


def test_sway_rotates_sprite_item_transform(qtbot, sprite_path) -> None:
    """A single large advance() step is guaranteed to land inside a
    sway (max wait is 20s). The tilt eases in from 0 at the exact
    trigger instant, so a small follow-up step is needed to observe it
    mid-ease, where it's virtually certain to be non-zero."""
    window = PetWindow(sprite_path)
    qtbot.addWidget(window)

    window.advance(20.5)  # exceeds the 8-20s max sway wait; triggers a sway
    assert window._sway.is_swaying is True

    window.advance(0.3)  # step partway into the ease-in
    assert window._sway.is_swaying is True
    assert window._sway.tilt_degrees != 0.0

    transform = window._sprite_item.transform()
    # A pure rotation changes the off-diagonal matrix elements away
    # from the identity's (m12=0, m21=0).
    assert (transform.m12(), transform.m21()) != (0.0, 0.0)


def test_idle_animations_never_exceed_their_bounds_over_time(qtbot, sprite_path) -> None:
    """Runs a longer simulated stretch (well beyond any single wait
    range) and checks every animation stays within its documented
    bounds throughout - a smoke test against jitter/overshoot."""
    window = PetWindow(sprite_path)
    qtbot.addWidget(window)
    base_y = window._base_y

    for _ in range(60 * 30):  # 30 simulated seconds at 60fps
        window.advance(1 / 60)
        assert abs(window.y() - base_y) <= 4.0
        assert 0.0 < window._blink.scale_y <= 1.0
        assert abs(window._sway.tilt_degrees) <= 3.0001


# -- PNG loading, invalid image fallback, transparency ---------------------


def test_successful_png_loading_preserves_aspect_ratio(qtbot, tmp_path) -> None:
    """A valid, non-square PNG must be scaled to fit inside the target
    box without being stretched into a square."""
    sprite_file = tmp_path / "wide_sprite.png"
    _write_test_png(sprite_file, width=200, height=100, fill_argb=(255, 0, 0, 255))

    window = PetWindow(sprite_file)
    qtbot.addWidget(window)

    pixmap = window._sprite_item.pixmap()
    assert not pixmap.isNull()
    # 200x100 fit within 128x128 preserving a 2:1 aspect ratio -> 128x64.
    assert pixmap.width() == DEFAULT_SPRITE_SIZE
    assert pixmap.height() == DEFAULT_SPRITE_SIZE // 2
    # The window itself still matches the configured target size, with
    # the (now-narrower) sprite centered inside it.
    assert window.width() == DEFAULT_SPRITE_SIZE
    assert window.height() == DEFAULT_SPRITE_SIZE


def test_invalid_image_falls_back_without_crashing(qtbot, tmp_path, caplog) -> None:
    """A corrupt/invalid PNG must never crash the app - it should log a
    warning and fall back to the placeholder sprite instead."""
    corrupt_file = tmp_path / "corrupt.png"
    corrupt_file.write_bytes(b"this is not a valid png file")

    with caplog.at_level(logging.WARNING, logger="desktop_pet.ui.pet_window"):
        window = PetWindow(corrupt_file)
    qtbot.addWidget(window)

    pixmap = window._sprite_item.pixmap()
    assert pixmap is not None
    assert not pixmap.isNull()
    assert any("Could not load pet sprite" in message for message in caplog.messages)


def test_all_candidates_failing_uses_emergency_pixmap_without_crashing(
    qtbot, tmp_path, caplog
) -> None:
    """Even if both the primary sprite and the placeholder fail to load,
    the window must still open rather than crash."""
    missing_primary = tmp_path / "missing_primary.png"
    missing_fallback = tmp_path / "missing_fallback.png"

    with caplog.at_level(logging.WARNING, logger="desktop_pet.ui.pet_window"):
        window = PetWindow(missing_primary, fallback_sprite_path=missing_fallback)
    qtbot.addWidget(window)

    pixmap = window._sprite_item.pixmap()
    assert not pixmap.isNull()
    assert pixmap.width() == DEFAULT_SPRITE_SIZE
    assert pixmap.height() == DEFAULT_SPRITE_SIZE
    assert any("emergency sprite" in message for message in caplog.messages)


def test_transparency_is_preserved(qtbot, tmp_path) -> None:
    """Requirement: transparency in the source PNG must survive loading
    and scaling, not get flattened onto an opaque background."""
    sprite_file = tmp_path / "transparent_sprite.png"

    size = 64
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))  # fully transparent
    center_margin = size // 4
    for x in range(center_margin, size - center_margin):
        for y in range(center_margin, size - center_margin):
            image.setPixelColor(x, y, QColor(0, 200, 0, 255))  # opaque center
    assert image.save(str(sprite_file), "PNG")

    window = PetWindow(sprite_file)
    qtbot.addWidget(window)

    pixmap = window._sprite_item.pixmap()
    assert pixmap.hasAlphaChannel()

    result_image = pixmap.toImage()
    corner_alpha = result_image.pixelColor(1, 1).alpha()
    center_alpha = result_image.pixelColor(
        result_image.width() // 2, result_image.height() // 2
    ).alpha()

    assert corner_alpha == 0
    assert center_alpha == 255
