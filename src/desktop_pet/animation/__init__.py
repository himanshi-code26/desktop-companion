"""
desktop_pet.animation
========================

The pet's animation subsystem. Currently home to the idle animations
(breathing, blinking, sway) — see ``animation.idle``. Sprite-sheet
frame playback and blending, referenced in the project roadmap, will
be added here in a later phase.
"""

from desktop_pet.animation.idle import BlinkScheduler, BreathingAnimation, SwayAnimation

__all__ = ["BlinkScheduler", "BreathingAnimation", "SwayAnimation"]
