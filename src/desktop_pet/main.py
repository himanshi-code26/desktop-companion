"""
desktop_pet.main
=================

Application entry point.

Bootstrap (Phase 1) + window launch (Phase 2)
----------------------------------------------
This project is being built incrementally. Before anything touches Qt,
``main()`` still runs the Phase 1 bootstrap:

1. verifies the Python interpreter is new enough,
2. verifies every required third-party dependency is importable and
   logs its version (so users get a clear, actionable error instead of
   a stack trace if something is missing),
3. sets up structured logging that the rest of the app reuses.

Once the environment is confirmed healthy, Phase 2 takes over: it
builds the composition root (``desktop_pet.core.app.Application``),
which creates the transparent always-on-top pet window and starts the
60 FPS game loop.

Run it with:
    python -m desktop_pet.main
or, once installed:
    desktop-pet
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version as pkg_version

MIN_PYTHON = (3, 11)

# Maps the pip/PyPI distribution name -> the importable module name.
# Some packages differ (e.g. "pygame-ce" is imported as "pygame").
REQUIRED_DEPENDENCIES: dict[str, str] = {
    "PySide6": "PySide6",
    "Pillow": "PIL",
    "pygame-ce": "pygame",
    "pynput": "pynput",
    "PyAutoGUI": "pyautogui",
    "screeninfo": "screeninfo",
    "numpy": "numpy",
}

logger = logging.getLogger("desktop_pet")


@dataclass(frozen=True)
class DependencyStatus:
    """Result of checking a single dependency."""

    distribution_name: str
    module_name: str
    installed: bool
    version: str | None
    error: str | None = None


def configure_logging(level: int = logging.INFO) -> None:
    """Set up a single, consistent logging format for the whole app.

    Every subsystem added in later phases should call
    ``logging.getLogger("desktop_pet.<subsystem>")`` rather than
    configuring its own handlers, so log output stays uniform.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def check_python_version() -> bool:
    """Return True if the running interpreter meets MIN_PYTHON."""
    if sys.version_info[:2] < MIN_PYTHON:
        logger.error(
            "Python %s.%s+ is required, but %s.%s is running.",
            *MIN_PYTHON,
            sys.version_info.major,
            sys.version_info.minor,
        )
        return False
    logger.info(
        "Python version OK (%s.%s.%s)",
        sys.version_info.major,
        sys.version_info.minor,
        sys.version_info.micro,
    )
    return True


def check_dependencies() -> list[DependencyStatus]:
    """Import every required dependency and record its status.

    This never raises — it collects results for all dependencies so a
    user missing three packages sees all three at once, not just the
    first one that fails.
    """
    results: list[DependencyStatus] = []
    for distribution_name, module_name in REQUIRED_DEPENDENCIES.items():
        try:
            import_module(module_name)
            try:
                resolved_version = pkg_version(distribution_name)
            except PackageNotFoundError:
                resolved_version = "unknown"
            results.append(
                DependencyStatus(
                    distribution_name=distribution_name,
                    module_name=module_name,
                    installed=True,
                    version=resolved_version,
                )
            )
            logger.info("Dependency OK: %-12s (%s)", distribution_name, resolved_version)
        except ImportError as exc:
            results.append(
                DependencyStatus(
                    distribution_name=distribution_name,
                    module_name=module_name,
                    installed=False,
                    version=None,
                    error=str(exc),
                )
            )
            logger.error("Dependency MISSING: %s (%s)", distribution_name, exc)
    return results


def print_startup_banner() -> None:
    from desktop_pet import __version__

    banner = (
        "\n"
        "=========================================\n"
        f"  Desktop Pet  v{__version__}\n"
        "  A free & open-source virtual companion\n"
        "=========================================\n"
    )
    print(banner)


def main() -> int:
    """Bootstrap entry point.

    Returns a process exit code (0 = success) so ``sys.exit(main())``
    behaves correctly for both ``python -m desktop_pet.main`` and the
    installed ``desktop-pet`` console script.
    """
    configure_logging()
    print_startup_banner()

    if not check_python_version():
        return 1

    results = check_dependencies()
    missing = [r for r in results if not r.installed]
    if missing:
        logger.error(
            "Cannot start: %d required dependenc%s missing. "
            "Run `pip install -r requirements.txt` and try again.",
            len(missing),
            "y is" if len(missing) == 1 else "ies are",
        )
        return 1

    logger.info("Environment verified. Launching window...")

    from desktop_pet.core.app import Application

    application = Application()
    return application.run()


if __name__ == "__main__":
    sys.exit(main())
