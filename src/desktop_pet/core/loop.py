"""
desktop_pet.core.loop
========================

A fixed-rate game loop built on top of Qt's own event loop (no extra
thread). Every tick, every subscribed callback receives the *real*
elapsed time since the previous tick (delta_time, in seconds) rather
than an assumed fixed step — so animation, physics, and behavior
(added in later phases) stay smooth and frame-rate independent even
if a frame is delayed.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QElapsedTimer, Qt, QTimer

FrameCallback = Callable[[float], None]


class GameLoop:
    """Ticks at ``target_fps`` and notifies subscribers with delta_time."""

    def __init__(self, target_fps: int = 60) -> None:
        if target_fps <= 0:
            raise ValueError("target_fps must be positive")

        self._target_fps = target_fps
        self._callbacks: list[FrameCallback] = []

        self._timer = QTimer()
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._on_tick)

        self._elapsed_timer = QElapsedTimer()

    @property
    def target_fps(self) -> int:
        return self._target_fps

    def subscribe(self, callback: FrameCallback) -> None:
        """Register a callback to be invoked every tick as callback(delta_time)."""
        self._callbacks.append(callback)

    def start(self) -> None:
        self._elapsed_timer.start()
        interval_ms = round(1000 / self._target_fps)
        self._timer.start(interval_ms)

    def stop(self) -> None:
        self._timer.stop()

    def is_running(self) -> bool:
        return self._timer.isActive()

    def _on_tick(self) -> None:
        elapsed_ms = self._elapsed_timer.restart()
        delta_time = elapsed_ms / 1000.0
        for callback in self._callbacks:
            callback(delta_time)
