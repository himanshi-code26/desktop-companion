"""
desktop_pet
===========

A free, open-source, physics-based, AI-behavior desktop pet companion.

This package is organized into independent subsystems so that each one
can be developed, tested, and swapped out without touching the others:

- ``core``      : application bootstrap, dependency injection, event bus
- ``physics``   : gravity, velocity, collision, screen-edge detection
- ``animation`` : sprite sheet loading, frame playback, blending
- ``audio``     : sound effect playback and volume control
- ``behavior``  : the pet's state machine / behavior tree ("AI")
- ``ui``        : the transparent always-on-top window and rendering surface

Nothing in this package should ever import directly from another
subsystem's internals — subsystems communicate only through the
event bus and well-defined interfaces (see ``core.events`` and
``core.interfaces``, introduced in later phases). This keeps the
project free of circular dependencies and spaghetti code as it grows.
"""

__version__ = "0.1.0"
__author__ = "Desktop Pet Contributors"
__license__ = "MIT"
