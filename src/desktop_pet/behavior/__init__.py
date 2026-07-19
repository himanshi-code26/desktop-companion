"""
desktop_pet.behavior
=======================

The pet's reactive behavior subsystem. Currently home to cursor
awareness (see ``behavior.cursor_attention``) — a lightweight, purely
reactive response to cursor distance and stillness, not a full
AI/state-machine behavior engine (that's reserved for a later phase).
"""

from desktop_pet.behavior.cursor_attention import CursorAttention

__all__ = ["CursorAttention"]
