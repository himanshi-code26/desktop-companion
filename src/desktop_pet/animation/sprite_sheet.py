"""
desktop_pet.animation.sprite_sheet
===================================

Sprite sheet frame extraction, animation clips, and delta-time frame playback.

This module provides plain Python abstractions for 2D sprite animations:

- ``AnimationFrame``: bounding box (x, y, width, height) of a single frame.
- ``SpriteSheet``: grid or JSON atlas parser dividing an image into frames.
- ``AnimationClip``: a named sequence of frame indices with FPS, looping,
  and optional chaining settings.
- ``SpriteAnimator``: stateful animation controller driven by delta-time tick
  updates. Fully decoupled from Qt rendering, enabling 100% headless testing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from desktop_pet.ai.event_bus import EventBus
from desktop_pet.ai.events import Event, EventType

logger = logging.getLogger("desktop_pet.animation.sprite_sheet")


@dataclass(frozen=True)
class AnimationFrame:
    """Bounding box definition for a single frame within a sprite sheet.

    Attributes:
        index: Zero-based index of the frame in the sprite sheet.
        x: X-coordinate of top-left corner in pixels.
        y: Y-coordinate of top-left corner in pixels.
        width: Width of the frame in pixels.
        height: Height of the frame in pixels.
    """

    index: int
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("index must be >= 0")
        if self.x < 0 or self.y < 0:
            raise ValueError("x and y coordinates must be >= 0")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be > 0")


class SpriteSheet:
    """Manages frame regions within a sprite sheet image grid or JSON atlas."""

    def __init__(
        self,
        sheet_width: int,
        sheet_height: int,
        frames: list[AnimationFrame],
    ) -> None:
        """
        Args:
            sheet_width: Total image width in pixels.
            sheet_height: Total image height in pixels.
            frames: List of ``AnimationFrame`` bounding boxes.
        """
        if sheet_width <= 0 or sheet_height <= 0:
            raise ValueError("sheet_width and sheet_height must be positive")
        if not frames:
            raise ValueError("frames list cannot be empty")

        self._sheet_width = sheet_width
        self._sheet_height = sheet_height
        self._frames = list(frames)

    @property
    def sheet_width(self) -> int:
        return self._sheet_width

    @property
    def sheet_height(self) -> int:
        return self._sheet_height

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    @property
    def frames(self) -> list[AnimationFrame]:
        return list(self._frames)

    def get_frame(self, index: int) -> AnimationFrame:
        """Return the frame at ``index``. Raises IndexError if out of range."""
        if not (0 <= index < len(self._frames)):
            raise IndexError(f"Frame index {index} out of bounds (0..{len(self._frames) - 1})")
        return self._frames[index]

    @classmethod
    def from_grid(
        cls,
        sheet_width: int,
        sheet_height: int,
        columns: int,
        rows: int,
        frame_width: int | None = None,
        frame_height: int | None = None,
    ) -> SpriteSheet:
        """Create a uniform grid-based sprite sheet. Automatically infers frame dimensions
        from sheet dimensions and columns/rows if frame_width or frame_height are omitted.

        Args:
            sheet_width: Total image width in pixels.
            sheet_height: Total image height in pixels.
            columns: Number of frame columns across the sheet.
            rows: Number of frame rows down the sheet.
            frame_width: Optional frame width override (defaults to sheet_width // columns).
            frame_height: Optional frame height override (defaults to sheet_height // rows).
        """
        if columns <= 0 or rows <= 0:
            raise ValueError("columns and rows must be > 0")

        fw = frame_width if frame_width is not None else sheet_width // columns
        fh = frame_height if frame_height is not None else sheet_height // rows

        if fw <= 0 or fh <= 0:
            raise ValueError("Computed frame width and height must be > 0")

        frames: list[AnimationFrame] = []
        frame_idx = 0
        for r in range(rows):
            for c in range(columns):
                x = c * fw
                y = r * fh
                if x + fw > sheet_width or y + fh > sheet_height:
                    continue
                frames.append(
                    AnimationFrame(
                        index=frame_idx,
                        x=x,
                        y=y,
                        width=fw,
                        height=fh,
                    )
                )
                frame_idx += 1

        if not frames:
            raise ValueError("Grid parameters resulted in zero valid frames")

        return cls(sheet_width=sheet_width, sheet_height=sheet_height, frames=frames)

    @classmethod
    def from_image_dimensions(
        cls,
        width: int,
        height: int,
        columns: int = 8,
        rows: int = 4,
    ) -> SpriteSheet:
        """Convenience method to construct a SpriteSheet from dimensions without hardcoding frame size."""
        return cls.from_grid(sheet_width=width, sheet_height=height, columns=columns, rows=rows)

    @classmethod
    def from_atlas_data(cls, atlas_data: dict[str, Any]) -> SpriteSheet:
        """Parse JSON atlas metadata (TexturePacker format or frame array).

        Expected schema:
        ``{"meta": {"size": {"w": 256, "h": 256}}, "frames": [{"frame": {"x": 0, "y": 0, "w": 64, "h": 64}}, ...]}``
        or a list/dict of frame definitions.
        """
        meta = atlas_data.get("meta", {})
        size = meta.get("size", {})
        sheet_w = int(size.get("w", 0))
        sheet_h = int(size.get("h", 0))

        raw_frames = atlas_data.get("frames", [])
        parsed_frames: list[AnimationFrame] = []

        if isinstance(raw_frames, list):
            for idx, item in enumerate(raw_frames):
                f = item.get("frame", item) if isinstance(item, dict) else {}
                fx = int(f.get("x", 0))
                fy = int(f.get("y", 0))
                fw = int(f.get("w", f.get("width", 0)))
                fh = int(f.get("h", f.get("height", 0)))
                parsed_frames.append(
                    AnimationFrame(index=idx, x=fx, y=fy, width=fw, height=fh)
                )
        elif isinstance(raw_frames, dict):
            for idx, (name, item) in enumerate(raw_frames.items()):
                f = item.get("frame", item) if isinstance(item, dict) else {}
                fx = int(f.get("x", 0))
                fy = int(f.get("y", 0))
                fw = int(f.get("w", f.get("width", 0)))
                fh = int(f.get("h", f.get("height", 0)))
                parsed_frames.append(
                    AnimationFrame(index=idx, x=fx, y=fy, width=fw, height=fh)
                )

        if not sheet_w and parsed_frames:
            sheet_w = max(f.x + f.width for f in parsed_frames)
        if not sheet_h and parsed_frames:
            sheet_h = max(f.y + f.height for f in parsed_frames)

        return cls(sheet_width=sheet_w, sheet_height=sheet_h, frames=parsed_frames)


class AnimationClip:
    """Defines a sequence of frames for a specific animation state/action."""

    def __init__(
        self,
        name: str,
        frame_indices: list[int],
        fps: float = 10.0,
        loop: bool = True,
        next_clip: str | None = None,
    ) -> None:
        """
        Args:
            name: Identifier for this animation clip (e.g., "walk", "idle").
            frame_indices: Sequential list of sprite sheet frame indices.
            fps: Playback speed in frames per second.
            loop: Whether the animation loops continuously.
            next_clip: Name of clip to transition to upon non-looping completion.
        """
        if not name:
            raise ValueError("Clip name cannot be empty")
        if not frame_indices:
            raise ValueError("frame_indices cannot be empty")
        if fps <= 0:
            raise ValueError("fps must be > 0")

        self._name = name
        self._frame_indices = list(frame_indices)
        self._fps = fps
        self._loop = loop
        self._next_clip = next_clip

    @property
    def name(self) -> str:
        return self._name

    @property
    def frame_indices(self) -> list[int]:
        return list(self._frame_indices)

    @property
    def frame_count(self) -> int:
        return len(self._frame_indices)

    @property
    def fps(self) -> float:
        return self._fps

    @fps.setter
    def fps(self, new_fps: float) -> None:
        if new_fps <= 0:
            raise ValueError("fps must be > 0")
        self._fps = float(new_fps)

    @property
    def frame_duration(self) -> float:
        """Seconds per individual frame."""
        return 1.0 / self._fps

    @property
    def total_duration(self) -> float:
        """Total duration of one full pass in seconds."""
        return len(self._frame_indices) * self.frame_duration

    @property
    def loop(self) -> bool:
        return self._loop

    @property
    def next_clip(self) -> str | None:
        return self._next_clip


class SpriteAnimator:
    """Controls frame playback and state transitions driven by delta-time updates.

    Decoupled from render engine/physics, supporting looping, one-shot animations,
    pause/resume/restart, and graceful idle fallback.
    """

    def __init__(
        self,
        sprite_sheet: SpriteSheet | None = None,
        clips: dict[str, AnimationClip] | None = None,
        default_clip: str | None = "idle",
        event_bus: EventBus | None = None,
    ) -> None:
        """
        Args:
            sprite_sheet: The underlying ``SpriteSheet`` source.
            clips: Dictionary mapping clip names to ``AnimationClip`` instances.
            default_clip: Clip name to play automatically & use as fallback.
            event_bus: Optional ``EventBus`` to subscribe to ``STATE_CHANGED`` events.
        """
        self._sprite_sheet = sprite_sheet
        self._clips: dict[str, AnimationClip] = {}
        self._default_clip = default_clip

        if clips:
            for clip in clips.values():
                self.add_clip(clip)

        self._current_clip: AnimationClip | None = None
        self._current_frame_step: int = 0
        self._elapsed_in_frame: float = 0.0
        self._is_playing: bool = False
        self._is_finished: bool = False

        self._event_bus = event_bus
        if self._event_bus is not None:
            self._event_bus.subscribe(EventType.STATE_CHANGED, self._on_state_changed)

        if default_clip and default_clip in self._clips:
            self.play(default_clip)

    @property
    def sprite_sheet(self) -> SpriteSheet | None:
        return self._sprite_sheet

    @sprite_sheet.setter
    def sprite_sheet(self, sheet: SpriteSheet) -> None:
        self._sprite_sheet = sheet

    @property
    def default_clip(self) -> str | None:
        return self._default_clip

    @default_clip.setter
    def default_clip(self, clip_name: str | None) -> None:
        self._default_clip = clip_name

    def add_clip(self, clip: AnimationClip) -> None:
        """Register a new ``AnimationClip``."""
        self._clips[clip.name] = clip
        logger.debug("Registered AnimationClip '%s' (%d frames, %.1f FPS)", clip.name, clip.frame_count, clip.fps)

    def _format_clip_key(self, name: str | Any) -> str:
        if hasattr(name, "value"):
            return str(name.value).lower()
        return str(name).lower()

    def has_clip(self, name: str | Any) -> bool:
        key = self._format_clip_key(name)
        return key in self._clips

    def get_clip(self, name: str | Any) -> AnimationClip | None:
        key = self._format_clip_key(name)
        return self._clips.get(key)

    @property
    def current_clip_name(self) -> str | None:
        return self._current_clip.name if self._current_clip is not None else None

    @property
    def current_clip(self) -> AnimationClip | None:
        return self._current_clip

    @property
    def current_clip_frame_index(self) -> int:
        """Step index within the active clip (0 .. clip.frame_count - 1)."""
        return self._current_frame_step

    @property
    def current_sheet_frame_index(self) -> int:
        """Frame index within the underlying ``SpriteSheet``."""
        if self._current_clip is None:
            return 0
        return self._current_clip.frame_indices[self._current_frame_step]

    @property
    def current_frame_rect(self) -> AnimationFrame | None:
        """Current ``AnimationFrame`` region from the sprite sheet."""
        if self._sprite_sheet is None:
            return None
        sheet_idx = self.current_sheet_frame_index
        return self._sprite_sheet.get_frame(sheet_idx)

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @property
    def is_finished(self) -> bool:
        return self._is_finished

    def play(
        self,
        clip_name: str | Any,
        restart: bool = False,
        fallback: str | None = "idle",
    ) -> None:
        """Switch to and play ``clip_name``. If ``clip_name`` is not registered,
        falls back gracefully to ``fallback`` (default "idle") if available.

        Args:
            clip_name: Clip name or PetState enum value to play.
            restart: If True, restarts even if already playing this clip.
            fallback: Optional clip name to play if clip_name is missing.
        """
        key = self._format_clip_key(clip_name)

        target_key = key
        if target_key not in self._clips:
            fallback_key = self._format_clip_key(fallback) if fallback else self._default_clip
            if fallback_key and fallback_key in self._clips:
                logger.info(
                    "Requested clip '%s' not registered. Falling back to default clip '%s'",
                    key,
                    fallback_key,
                )
                target_key = fallback_key
            else:
                raise KeyError(
                    f"No animation clip registered for '{key}' and fallback '{fallback_key}' is unavailable."
                )

        if self._current_clip is not None and self._current_clip.name == target_key and not restart:
            # Maintain active playback without flicker or state reset
            if not self._is_playing and not self._is_finished:
                self._is_playing = True
            return

        self._current_clip = self._clips[target_key]
        self._current_frame_step = 0
        self._elapsed_in_frame = 0.0
        self._is_playing = True
        self._is_finished = False
        logger.info("Playing animation clip '%s' (requested: '%s')", target_key, key)

    def pause(self) -> None:
        """Pause playback at current frame."""
        self._is_playing = False

    def resume(self) -> None:
        """Resume playback from current frame."""
        if self._current_clip is not None and not self._is_finished:
            self._is_playing = True

    def restart(self) -> None:
        """Restart active clip from frame 0."""
        if self._current_clip is not None:
            self._current_frame_step = 0
            self._elapsed_in_frame = 0.0
            self._is_playing = True
            self._is_finished = False

    def stop(self) -> None:
        """Stop playback and reset frame pointer."""
        self._is_playing = False
        self._current_frame_step = 0
        self._elapsed_in_frame = 0.0

    def advance(self, delta_time: float) -> None:
        """Advance animation playback by ``delta_time`` seconds."""
        if not self._is_playing or self._current_clip is None:
            return

        clip = self._current_clip
        self._elapsed_in_frame += delta_time
        frame_duration = clip.frame_duration

        while self._elapsed_in_frame + 1e-7 >= frame_duration:
            self._elapsed_in_frame -= frame_duration
            if self._elapsed_in_frame < 0:
                self._elapsed_in_frame = 0.0
            self._current_frame_step += 1

            if self._current_frame_step >= clip.frame_count:
                if clip.loop:
                    self._current_frame_step = 0
                else:
                    self._current_frame_step = clip.frame_count - 1
                    self._is_playing = False
                    self._is_finished = True

                    if clip.next_clip and self.has_clip(clip.next_clip):
                        self.play(clip.next_clip)
                    break

    def _on_state_changed(self, event: Event) -> None:
        """Auto-play animation matching state transitions from ``EventBus``.

        If state has no matching clip, gracefully falls back to idle animation.
        """
        new_state = event.payload.get("new_state")
        if new_state is None:
            return
        state_name = getattr(new_state, "value", str(new_state))
        self.play(state_name, fallback=self._default_clip or "idle")


def build_default_pet_sprite_sheet(width: int = 1536, height: int = 1024) -> tuple[SpriteSheet, dict[str, AnimationClip]]:
    """Build standard 4x8 SpriteSheet and AnimationClips matching the repository sprite sheet layout."""
    sheet = SpriteSheet.from_image_dimensions(width, height, columns=8, rows=4)

    clips = {
        "idle": AnimationClip("idle", frame_indices=[0, 1, 2], fps=4.0, loop=True),
        "blink": AnimationClip("blink", frame_indices=[0, 3, 4, 5, 6, 7, 0], fps=8.0, loop=False, next_clip="idle"),
        "walk": AnimationClip("walk", frame_indices=list(range(8, 16)), fps=10.0, loop=True),
        "stand": AnimationClip("stand", frame_indices=[16, 17], fps=2.0, loop=True),
        "sleep": AnimationClip("sleep", frame_indices=list(range(24, 30)), fps=4.0, loop=True),
    }

    return sheet, clips

