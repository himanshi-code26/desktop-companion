"""Unit tests for desktop_pet.core.app's sprite discovery logic."""

from __future__ import annotations

from pathlib import Path

from desktop_pet.core import app as app_module


def test_discover_returns_none_when_default_pet_dir_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(app_module, "get_assets_dir", lambda: tmp_path)
    assert app_module._discover_default_pet_sprite() is None


def test_discover_returns_none_when_default_pet_dir_empty(monkeypatch, tmp_path) -> None:
    (tmp_path / "pets" / "default").mkdir(parents=True)
    monkeypatch.setattr(app_module, "get_assets_dir", lambda: tmp_path)
    assert app_module._discover_default_pet_sprite() is None


def test_discover_ignores_non_png_files(monkeypatch, tmp_path) -> None:
    default_dir = tmp_path / "pets" / "default"
    default_dir.mkdir(parents=True)
    (default_dir / "readme.txt").write_text("not an image")
    monkeypatch.setattr(app_module, "get_assets_dir", lambda: tmp_path)
    assert app_module._discover_default_pet_sprite() is None


def test_discover_picks_first_png_alphabetically(monkeypatch, tmp_path) -> None:
    default_dir = tmp_path / "pets" / "default"
    default_dir.mkdir(parents=True)
    (default_dir / "zebra.png").write_bytes(b"fake png bytes")
    (default_dir / "apple.png").write_bytes(b"fake png bytes")
    (default_dir / "mango.png").write_bytes(b"fake png bytes")
    monkeypatch.setattr(app_module, "get_assets_dir", lambda: tmp_path)

    result = app_module._discover_default_pet_sprite()

    assert result == default_dir / "apple.png"


def test_resolve_sprite_path_prefers_default_pet_dir(monkeypatch, tmp_path) -> None:
    default_dir = tmp_path / "pets" / "default"
    default_dir.mkdir(parents=True)
    sticker = default_dir / "sticker.png"
    sticker.write_bytes(b"fake png bytes")
    monkeypatch.setattr(app_module, "get_assets_dir", lambda: tmp_path)

    assert app_module.resolve_sprite_path() == sticker


def test_resolve_sprite_path_falls_back_to_placeholder(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(app_module, "get_assets_dir", lambda: tmp_path)
    placeholder = Path("/fake/placeholder_pet.png")
    monkeypatch.setattr(app_module, "get_placeholder_sprite_path", lambda: placeholder)

    assert app_module.resolve_sprite_path() == placeholder


def test_compute_target_size_at_default_scale_matches_default_sprite_size() -> None:
    assert app_module._compute_target_size(1.0) == app_module.DEFAULT_SPRITE_SIZE


def test_compute_target_size_doubles_at_scale_two() -> None:
    assert app_module._compute_target_size(2.0) == app_module.DEFAULT_SPRITE_SIZE * 2


def test_compute_target_size_halves_at_scale_half() -> None:
    assert app_module._compute_target_size(0.5) == app_module.DEFAULT_SPRITE_SIZE // 2


def test_compute_target_size_rounds_to_nearest_whole_pixel() -> None:
    assert app_module._compute_target_size(1.333) == round(app_module.DEFAULT_SPRITE_SIZE * 1.333)
