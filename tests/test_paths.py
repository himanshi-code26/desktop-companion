"""Unit tests for desktop_pet.core.paths."""

from __future__ import annotations

from desktop_pet.core.paths import (
    get_assets_dir,
    get_config_dir,
    get_placeholder_sprite_path,
    get_project_root,
)


def test_get_project_root_contains_pyproject_toml() -> None:
    root = get_project_root()
    assert (root / "pyproject.toml").exists()


def test_get_assets_dir_is_under_project_root() -> None:
    assets_dir = get_assets_dir()
    assert assets_dir == get_project_root() / "assets"


def test_get_config_dir_is_under_project_root() -> None:
    config_dir = get_config_dir()
    assert config_dir == get_project_root() / "config"
    assert (config_dir / "default_config.json").exists()


def test_default_pet_assets_exist() -> None:
    assets = get_assets_dir()

    assert (assets / "pets" / "default" / "sticker_boy.png").exists(), (
        "Default pet image is missing."
    )

    assert (assets / "sprites" / "spritesheet.png.png").exists(), (
        "Default sprite sheet is missing."
    )

def test_get_placeholder_sprite_path_matches_known_location() -> None:
    assert get_placeholder_sprite_path() == get_assets_dir() / "sprites" / "placeholder_pet.png"
