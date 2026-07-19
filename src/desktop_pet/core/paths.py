"""
desktop_pet.core.paths
========================

Central place for resolving filesystem paths (project root, assets,
config) so no other module has to guess based on the current working
directory.

This works when running from source (``python -m desktop_pet.main``).
Phase 10 (packaging) will extend this to also handle a frozen/installed
build, where assets are bundled differently — that logic belongs here,
not scattered across the codebase.
"""

from __future__ import annotations

from pathlib import Path

_MARKER_FILE = "pyproject.toml"


def get_project_root() -> Path:
    """Walk upward from this file until the repository root is found.

    The repository root is identified by the presence of
    ``pyproject.toml``, which only exists at the top of the repo.
    """
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / _MARKER_FILE).exists():
            return parent
    raise RuntimeError(
        f"Could not locate project root: no {_MARKER_FILE} found above {current}"
    )


def get_assets_dir() -> Path:
    """Return the shared assets/ directory at the project root."""
    return get_project_root() / "assets"


def get_config_dir() -> Path:
    """Return the config/ directory at the project root."""
    return get_project_root() / "config"


def get_placeholder_sprite_path() -> Path:
    """Return the path to the built-in, generated placeholder sprite.

    This is the last resort ``PetWindow`` falls back to if the
    configured pet sprite can't be loaded (missing file, corrupt PNG,
    etc.) — see ``ui.pet_window.PetWindow``. Keeping the path in one
    place avoids the same literal string being duplicated across
    ``core.app`` and ``ui.pet_window``.
    """
    return get_assets_dir() / "sprites" / "placeholder_pet.png"
