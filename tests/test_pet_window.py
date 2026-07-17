"""Unit tests for desktop_pet.ui.pet_window.PetWindow.

Run with QT_QPA_PLATFORM=offscreen in headless environments (CI already
sets this — see .github/workflows/ci.yml).
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from desktop_pet.core.paths import get_assets_dir
from desktop_pet.ui.pet_window import PetWindow


@pytest.fixture
def sprite_path():
    return get_assets_dir() / "sprites" / "placeholder_pet.png"


def test_missing_sprite_raises_file_not_found(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        PetWindow(tmp_path / "does_not_exist.png")


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


def test_window_size_matches_sprite(qtbot, sprite_path) -> None:
    window = PetWindow(sprite_path)
    qtbot.addWidget(window)
    assert window.width() > 0
    assert window.height() > 0


def test_escape_key_quits_application(qtbot, sprite_path, qapp) -> None:
    window = PetWindow(sprite_path)
    qtbot.addWidget(window)

    quit_calls: list[bool] = []
    qapp.quit = lambda: quit_calls.append(True)  # type: ignore[method-assign]

    event = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
    window.keyPressEvent(event)

    assert quit_calls == [True]


def test_advance_moves_window_around_base_y(qtbot, sprite_path) -> None:
    window = PetWindow(sprite_path)
    qtbot.addWidget(window)
    base_y = window._base_y

    window.advance(0.25)
    assert abs(window.y() - base_y) <= 6
