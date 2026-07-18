"""
tests/conftest.py
====================

Shared pytest configuration.

This only ever *reads or defaults* environment variables via
``os.environ.setdefault`` — never direct bracket access — so it can
never raise a ``KeyError`` itself, and it never overwrites a value a
developer or CI job has already set intentionally.

Two variables matter for running the Qt-based test suite on a
headless Linux machine (no X server) that isn't already running under
``xvfb-run`` (CI uses ``xvfb-run`` explicitly - see
``.github/workflows/ci.yml`` - so these defaults mostly help local
contributors):

- ``QT_QPA_PLATFORM=offscreen`` lets PySide6 run without any display
  server at all.
- ``DISPLAY`` is set to a harmless placeholder so that libraries which
  read ``os.environ['DISPLAY']`` directly at import time (e.g.
  pyautogui's Xlib backend) don't raise an uncaught ``KeyError`` before
  our own, broader exception handling in
  ``desktop_pet.main.check_dependencies`` ever gets a chance to run.
"""

from __future__ import annotations

import os
import sys

if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("DISPLAY", ":99")
