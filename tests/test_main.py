"""Unit tests for desktop_pet.main (Phase 1: bootstrap only)."""

from __future__ import annotations

import sys

import pytest

from desktop_pet.main import (
    MIN_PYTHON,
    REQUIRED_DEPENDENCIES,
    check_dependencies,
    check_python_version,
    main,
)


def test_min_python_is_reasonable() -> None:
    """Guard against someone accidentally lowering the floor unintentionally."""
    assert MIN_PYTHON >= (3, 11)


def test_current_interpreter_passes_version_check() -> None:
    # The test suite itself only runs on a supported interpreter, so this
    # should always be true in CI.
    assert sys.version_info[:2] >= MIN_PYTHON
    assert check_python_version() is True


def test_required_dependencies_non_empty() -> None:
    assert len(REQUIRED_DEPENDENCIES) > 0


def test_check_dependencies_returns_one_result_per_dependency() -> None:
    results = check_dependencies()
    assert len(results) == len(REQUIRED_DEPENDENCIES)
    for result in results:
        assert result.distribution_name in REQUIRED_DEPENDENCIES


def test_check_dependencies_all_installed_in_dev_env() -> None:
    """This test assumes `pip install -r requirements.txt` has been run.

    If it fails locally, install the dependencies first — that's the
    exact failure mode this check is designed to surface for real users.
    """
    results = check_dependencies()
    missing = [r.distribution_name for r in results if not r.installed]
    assert not missing, f"Missing dependencies: {missing}"


def test_main_launches_application_when_environment_is_healthy(monkeypatch) -> None:
    """main() now hands off to Application.run() once the environment is
    verified. Application.run() drives a real Qt event loop, so it is
    mocked here — this test only checks the *handoff*, not window
    behavior (that belongs in tests/test_pet_window.py).
    """
    launched: dict[str, bool] = {"run_called": False}

    class FakeApplication:
        def __init__(self, argv=None) -> None:
            pass

        def run(self) -> int:
            launched["run_called"] = True
            return 0

    monkeypatch.setattr("desktop_pet.core.app.Application", FakeApplication)
    assert main() == 0
    assert launched["run_called"] is True


@pytest.mark.parametrize("bad_version", [(2, 7), (3, 6), (3, 10)])
def test_check_python_version_rejects_old_versions(monkeypatch, bad_version) -> None:
    monkeypatch.setattr(sys, "version_info", bad_version + (0, "final", 0))
    assert check_python_version() is False
