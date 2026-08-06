"""Unit tests for desktop_pet.animation.sprite_sheet."""

from __future__ import annotations

import pytest

from desktop_pet.ai.event_bus import EventBus
from desktop_pet.ai.events import Event, EventType
from desktop_pet.ai.state import PetState
from desktop_pet.animation.sprite_sheet import (
    AnimationClip,
    AnimationFrame,
    SpriteAnimator,
    SpriteSheet,
)


def test_animation_frame_validation() -> None:
    frame = AnimationFrame(index=0, x=10, y=20, width=32, height=32)
    assert frame.index == 0
    assert frame.x == 10
    assert frame.y == 20
    assert frame.width == 32
    assert frame.height == 32

    with pytest.raises(ValueError):
        AnimationFrame(index=-1, x=0, y=0, width=32, height=32)

    with pytest.raises(ValueError):
        AnimationFrame(index=0, x=-5, y=0, width=32, height=32)

    with pytest.raises(ValueError):
        AnimationFrame(index=0, x=0, y=0, width=0, height=32)


def test_sprite_sheet_from_grid() -> None:
    sheet = SpriteSheet.from_grid(
        sheet_width=128, sheet_height=64, columns=4, rows=2
    )
    assert sheet.sheet_width == 128
    assert sheet.sheet_height == 64
    assert sheet.frame_count == 8

    f0 = sheet.get_frame(0)
    assert f0.x == 0 and f0.y == 0 and f0.width == 32 and f0.height == 32

    f5 = sheet.get_frame(5)
    assert f5.x == 32 and f5.y == 32 and f5.width == 32 and f5.height == 32

    with pytest.raises(IndexError):
        sheet.get_frame(8)


def test_sprite_sheet_from_atlas_data() -> None:
    atlas_data = {
        "meta": {"size": {"w": 256, "h": 256}},
        "frames": [
            {"frame": {"x": 0, "y": 0, "w": 64, "h": 64}},
            {"frame": {"x": 64, "y": 0, "w": 64, "h": 64}},
        ],
    }
    sheet = SpriteSheet.from_atlas_data(atlas_data)
    assert sheet.frame_count == 2
    assert sheet.get_frame(0).width == 64
    assert sheet.get_frame(1).x == 64


def test_animation_clip_properties() -> None:
    clip = AnimationClip(name="walk", frame_indices=[0, 1, 2, 3], fps=10.0, loop=True)
    assert clip.name == "walk"
    assert clip.frame_indices == [0, 1, 2, 3]
    assert clip.fps == 10.0
    assert clip.frame_duration == pytest.approx(0.1)
    assert clip.total_duration == pytest.approx(0.4)
    assert clip.loop is True

    with pytest.raises(ValueError):
        AnimationClip(name="", frame_indices=[0])

    with pytest.raises(ValueError):
        AnimationClip(name="test", frame_indices=[])

    with pytest.raises(ValueError):
        AnimationClip(name="test", frame_indices=[0], fps=0)


def test_sprite_animator_playback() -> None:
    sheet = SpriteSheet.from_grid(128, 64, 4, 2)
    walk_clip = AnimationClip(name="walk", frame_indices=[0, 1, 2, 3], fps=10.0, loop=True)
    wave_clip = AnimationClip(
        name="wave", frame_indices=[4, 5], fps=5.0, loop=False, next_clip="walk"
    )

    animator = SpriteAnimator(
        sprite_sheet=sheet,
        clips={"walk": walk_clip, "wave": wave_clip},
        default_clip="walk",
    )

    assert animator.current_clip_name == "walk"
    assert animator.is_playing is True
    assert animator.current_clip_frame_index == 0
    assert animator.current_sheet_frame_index == 0

    # Advance by 0.1s (1 frame duration for walk)
    animator.advance(0.1)
    assert animator.current_clip_frame_index == 1
    assert animator.current_sheet_frame_index == 1

    # Advance past the last frame of walk loop
    animator.advance(0.3)
    assert animator.current_clip_frame_index == 0  # Looped back

    # Play wave (non-looping, transitions to walk)
    animator.play("wave")
    assert animator.current_clip_name == "wave"
    assert animator.current_sheet_frame_index == 4

    animator.advance(0.2)  # Frame 1 of wave
    assert animator.current_sheet_frame_index == 5

    animator.advance(0.2)  # End of wave -> auto switches to next_clip ("walk")
    assert animator.current_clip_name == "walk"
    assert animator.current_sheet_frame_index == 0


def test_sprite_animator_event_bus_integration() -> None:
    bus = EventBus()
    sheet = SpriteSheet.from_grid(128, 64, 4, 2)
    idle_clip = AnimationClip(name="idle", frame_indices=[0], fps=1.0)
    walk_clip = AnimationClip(name="walk", frame_indices=[1, 2], fps=10.0)

    animator = SpriteAnimator(
        sprite_sheet=sheet,
        clips={"idle": idle_clip, "walk": walk_clip},
        default_clip="idle",
        event_bus=bus,
    )

    assert animator.current_clip_name == "idle"

    # Emit STATE_CHANGED event on bus
    bus.publish(
        Event(
            EventType.STATE_CHANGED,
            {"previous_state": PetState.IDLE, "new_state": PetState.WALK},
            source="test",
        )
    )

    assert animator.current_clip_name == "walk"


def test_sprite_sheet_from_image_dimensions_infer_frame_size() -> None:
    sheet = SpriteSheet.from_image_dimensions(1536, 1024, columns=8, rows=4)
    assert sheet.sheet_width == 1536
    assert sheet.sheet_height == 1024
    assert sheet.frame_count == 32
    f0 = sheet.get_frame(0)
    assert f0.width == 192
    assert f0.height == 256
    f31 = sheet.get_frame(31)
    assert f31.x == 7 * 192
    assert f31.y == 3 * 256


def test_sprite_animator_playback_controls_and_pause_resume() -> None:
    sheet = SpriteSheet.from_grid(128, 64, 4, 2)
    clip = AnimationClip(name="idle", frame_indices=[0, 1, 2, 3], fps=10.0, loop=True)
    animator = SpriteAnimator(sprite_sheet=sheet, clips={"idle": clip}, default_clip="idle")

    assert animator.is_playing is True
    animator.pause()
    assert animator.is_playing is False

    animator.advance(0.5)
    assert animator.current_clip_frame_index == 0

    animator.resume()
    assert animator.is_playing is True

    animator.advance(0.1)
    assert animator.current_clip_frame_index == 1

    animator.restart()
    assert animator.current_clip_frame_index == 0

    animator.stop()
    assert animator.is_playing is False
    assert animator.current_clip_frame_index == 0


def test_sprite_animator_unmapped_state_falls_back_to_idle() -> None:
    bus = EventBus()
    sheet = SpriteSheet.from_grid(128, 64, 4, 2)
    idle_clip = AnimationClip(name="idle", frame_indices=[0], fps=1.0)
    walk_clip = AnimationClip(name="walk", frame_indices=[1, 2], fps=10.0)

    animator = SpriteAnimator(
        sprite_sheet=sheet,
        clips={"idle": idle_clip, "walk": walk_clip},
        default_clip="idle",
        event_bus=bus,
    )

    # Transition to an unmapped state (e.g. PetState.RUN or PetState.JUMP)
    bus.publish(
        Event(
            EventType.STATE_CHANGED,
            {"previous_state": PetState.IDLE, "new_state": PetState.RUN},
            source="test",
        )
    )

    # Must fall back gracefully to idle without error
    assert animator.current_clip_name == "idle"

    # Direct play with PetState enum
    animator.play(PetState.WALK)
    assert animator.current_clip_name == "walk"

    animator.play(PetState.JUMP)  # unmapped, falls back to idle
    assert animator.current_clip_name == "idle"


def test_build_default_pet_sprite_sheet() -> None:
    from desktop_pet.animation.sprite_sheet import build_default_pet_sprite_sheet

    sheet, clips = build_default_pet_sprite_sheet(1536, 1024)
    assert sheet.frame_count == 32
    assert "idle" in clips
    assert "walk" in clips
    assert "sleep" in clips
    assert "blink" in clips
    assert clips["walk"].frame_indices == list(range(8, 16))

