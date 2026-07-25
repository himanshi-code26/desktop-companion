"""Unit tests for desktop_pet.core.config."""

from __future__ import annotations

import json
import logging

from desktop_pet.core import config as config_module


def _write_config(tmp_path, data: dict) -> None:
    config_path = tmp_path / "default_config.json"
    config_path.write_text(json.dumps(data), encoding="utf-8")


def test_get_size_scale_reads_configured_value(monkeypatch, tmp_path) -> None:
    _write_config(tmp_path, {"window": {"size_scale": 2.0}})
    monkeypatch.setattr(config_module, "get_config_dir", lambda: tmp_path)
    assert config_module.get_size_scale() == 2.0


def test_get_size_scale_supports_half_scale(monkeypatch, tmp_path) -> None:
    _write_config(tmp_path, {"window": {"size_scale": 0.5}})
    monkeypatch.setattr(config_module, "get_config_dir", lambda: tmp_path)
    assert config_module.get_size_scale() == 0.5


def test_get_size_scale_defaults_to_one_when_key_missing(monkeypatch, tmp_path) -> None:
    _write_config(tmp_path, {"window": {}})
    monkeypatch.setattr(config_module, "get_config_dir", lambda: tmp_path)
    assert config_module.get_size_scale() == 1.0


def test_get_size_scale_defaults_when_window_section_missing(monkeypatch, tmp_path) -> None:
    _write_config(tmp_path, {})
    monkeypatch.setattr(config_module, "get_config_dir", lambda: tmp_path)
    assert config_module.get_size_scale() == 1.0


def test_get_size_scale_defaults_when_file_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(config_module, "get_config_dir", lambda: tmp_path)
    assert config_module.get_size_scale() == 1.0


def test_get_size_scale_defaults_when_json_is_malformed(monkeypatch, tmp_path, caplog) -> None:
    (tmp_path / "default_config.json").write_text("{ not valid json", encoding="utf-8")
    monkeypatch.setattr(config_module, "get_config_dir", lambda: tmp_path)

    with caplog.at_level(logging.WARNING, logger="desktop_pet.core.config"):
        result = config_module.get_size_scale()

    assert result == 1.0
    assert any("Could not load config" in message for message in caplog.messages)


def test_get_size_scale_defaults_when_value_is_not_a_number(monkeypatch, tmp_path, caplog) -> None:
    _write_config(tmp_path, {"window": {"size_scale": "huge"}})
    monkeypatch.setattr(config_module, "get_config_dir", lambda: tmp_path)

    with caplog.at_level(logging.WARNING, logger="desktop_pet.core.config"):
        result = config_module.get_size_scale()

    assert result == 1.0
    assert any("is not a number" in message for message in caplog.messages)


def test_get_size_scale_defaults_when_value_is_not_positive(monkeypatch, tmp_path, caplog) -> None:
    _write_config(tmp_path, {"window": {"size_scale": -1.0}})
    monkeypatch.setattr(config_module, "get_config_dir", lambda: tmp_path)

    with caplog.at_level(logging.WARNING, logger="desktop_pet.core.config"):
        result = config_module.get_size_scale()

    assert result == 1.0
    assert any("must be positive" in message for message in caplog.messages)


def test_get_ai_config_reads_configured_initial_state(monkeypatch, tmp_path) -> None:
    _write_config(tmp_path, {"ai": {"initial_state": "sleep"}})
    monkeypatch.setattr(config_module, "get_config_dir", lambda: tmp_path)
    assert config_module.get_ai_config() == {"initial_state": "sleep"}


def test_get_ai_config_defaults_when_ai_section_missing(monkeypatch, tmp_path) -> None:
    _write_config(tmp_path, {"window": {}})
    monkeypatch.setattr(config_module, "get_config_dir", lambda: tmp_path)
    assert config_module.get_ai_config() == config_module.DEFAULT_AI_CONFIG


def test_get_ai_config_defaults_when_file_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(config_module, "get_config_dir", lambda: tmp_path)
    assert config_module.get_ai_config() == config_module.DEFAULT_AI_CONFIG


def test_get_ai_config_defaults_when_section_is_not_an_object(monkeypatch, tmp_path, caplog) -> None:
    _write_config(tmp_path, {"ai": "not-an-object"})
    monkeypatch.setattr(config_module, "get_config_dir", lambda: tmp_path)

    with caplog.at_level(logging.WARNING, logger="desktop_pet.core.config"):
        result = config_module.get_ai_config()

    assert result == config_module.DEFAULT_AI_CONFIG
    assert any("is not an object" in message for message in caplog.messages)


def test_get_ai_config_merges_unknown_extra_keys(monkeypatch, tmp_path) -> None:
    _write_config(tmp_path, {"ai": {"future_key": "value"}})
    monkeypatch.setattr(config_module, "get_config_dir", lambda: tmp_path)

    result = config_module.get_ai_config()

    assert result["initial_state"] == "idle"
    assert result["future_key"] == "value"


def test_get_behavior_config_reads_configured_values(monkeypatch, tmp_path) -> None:
    _write_config(
        tmp_path,
        {"behavior": {"min_idle_seconds": 5.0, "max_idle_seconds": 10.0, "sleep_probability": 2.0}},
    )
    monkeypatch.setattr(config_module, "get_config_dir", lambda: tmp_path)

    result = config_module.get_behavior_config()

    assert result["min_idle_seconds"] == 5.0
    assert result["max_idle_seconds"] == 10.0
    assert result["sleep_probability"] == 2.0
    # Untouched keys still fall back to their defaults.
    assert result["read_probability"] == 1.0
    assert result["personality"] == "friendly"


def test_get_behavior_config_defaults_when_section_missing(monkeypatch, tmp_path) -> None:
    _write_config(tmp_path, {"window": {}})
    monkeypatch.setattr(config_module, "get_config_dir", lambda: tmp_path)
    assert config_module.get_behavior_config() == config_module.DEFAULT_BEHAVIOR_CONFIG


def test_get_behavior_config_defaults_when_file_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(config_module, "get_config_dir", lambda: tmp_path)
    assert config_module.get_behavior_config() == config_module.DEFAULT_BEHAVIOR_CONFIG


def test_get_behavior_config_defaults_when_section_is_not_an_object(
    monkeypatch, tmp_path, caplog
) -> None:
    _write_config(tmp_path, {"behavior": "not-an-object"})
    monkeypatch.setattr(config_module, "get_config_dir", lambda: tmp_path)

    with caplog.at_level(logging.WARNING, logger="desktop_pet.core.config"):
        result = config_module.get_behavior_config()

    assert result == config_module.DEFAULT_BEHAVIOR_CONFIG
    assert any("is not an object" in message for message in caplog.messages)