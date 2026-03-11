from __future__ import annotations

from pathlib import Path


def get_runtime_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "runtime"


def get_ready_flag() -> Path:
    return get_runtime_dir() / "backend_ready.flag"


def write_ready_flag() -> None:
    runtime_dir = get_runtime_dir()
    runtime_dir.mkdir(parents=True, exist_ok=True)

    flag = get_ready_flag()
    flag.write_text("READY\n", encoding="utf-8")


def clear_ready_flag() -> None:
    flag = get_ready_flag()
    try:
        if flag.exists():
            flag.unlink()
    except Exception:
        pass


def is_backend_ready() -> bool:
    return get_ready_flag().exists()