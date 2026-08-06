"""
desktop_pet.animation
========================

The pet's animation subsystem. Home to idle micro-animations (breathing,
blinking, sway), cursor awareness transforms, and sprite sheet frame
animation playback.
"""

from desktop_pet.animation.cursor_awareness import CursorAwareness, CursorZone
from desktop_pet.animation.idle import BlinkScheduler, BreathingAnimation, SwayAnimation
from desktop_pet.animation.sprite_sheet import (
    AnimationClip,
    AnimationFrame,
    SpriteAnimator,
    SpriteSheet,
)

__all__ = [
    "AnimationClip",
    "AnimationFrame",
    "BlinkScheduler",
    "BreathingAnimation",
    "CursorAwareness",
    "CursorZone",
    "SpriteAnimator",
    "SpriteSheet",
    "SwayAnimation",
]
