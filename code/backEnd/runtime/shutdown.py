# code/backEnd/runtime/shutdown.py

from __future__ import annotations

from pathlib import Path


def get_runtime_dir() -> Path:
    """
    Resolve the shared runtime directory.
    """

    return Path(__file__).resolve().parents[2] / "runtime"


def get_shutdown_flag_path() -> Path:
    """
    Resolve the graceful shutdown flag path.
    """

    return get_runtime_dir() / "shutdown.flag"


def shutdown_requested() -> bool:
    """
    Check whether a graceful shutdown has been requested.
    """

    return get_shutdown_flag_path().exists()


def clear_shutdown_flag() -> None:
    """
    Remove the shutdown flag if it exists.
    """

    shutdown_flag = get_shutdown_flag_path()

    try:
        if shutdown_flag.exists():
            shutdown_flag.unlink()
    except Exception:
        pass


def create_shutdown_flag() -> None:
    """
    Create the shutdown flag used to request graceful shutdown.
    """

    shutdown_flag = get_shutdown_flag_path()
    shutdown_flag.parent.mkdir(parents=True, exist_ok=True)
    shutdown_flag.touch(exist_ok=True)