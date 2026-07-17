"""Unit tests for desktop_pet.core.loop.

These use pytest-qt's `qapp`/`qtbot` fixtures, which provide a real
(offscreen, in CI) QApplication/event loop — GameLoop relies on Qt's
event loop being alive to fire QTimer callbacks.
"""

from __future__ import annotations

import pytest

from desktop_pet.core.loop import GameLoop


def test_target_fps_must_be_positive() -> None:
    with pytest.raises(ValueError):
        GameLoop(target_fps=0)
    with pytest.raises(ValueError):
        GameLoop(target_fps=-10)


def test_default_target_fps_is_60() -> None:
    loop = GameLoop()
    assert loop.target_fps == 60


def test_start_and_stop_toggle_is_running(qapp) -> None:
    loop = GameLoop(target_fps=60)
    assert loop.is_running() is False
    loop.start()
    assert loop.is_running() is True
    loop.stop()
    assert loop.is_running() is False


def test_subscribers_receive_positive_delta_time(qtbot) -> None:
    loop = GameLoop(target_fps=60)
    received_deltas: list[float] = []
    loop.subscribe(received_deltas.append)

    loop.start()
    qtbot.wait(100)  # let a handful of ~16.6ms ticks fire
    loop.stop()

    assert len(received_deltas) > 0
    assert all(delta_time > 0 for delta_time in received_deltas)


def test_multiple_subscribers_all_receive_ticks(qtbot) -> None:
    loop = GameLoop(target_fps=60)
    counts = {"a": 0, "b": 0}
    loop.subscribe(lambda dt: counts.__setitem__("a", counts["a"] + 1))
    loop.subscribe(lambda dt: counts.__setitem__("b", counts["b"] + 1))

    loop.start()
    qtbot.wait(100)
    loop.stop()

    assert counts["a"] > 0
    assert counts["a"] == counts["b"]
