# Purpose: Resolve the correct bundled MongoDB binary for the current OS.
# Inputs: RuntimePaths (location of runtime_binaries directory) and optional override from RuntimeConfig.
# Outputs: Absolute path to the mongod executable.

from __future__ import annotations

import platform
from pathlib import Path

from backEnd.runtime.config import RuntimeConfig
from backEnd.runtime.paths import RuntimePaths


def resolve_mongo_binary(cfg: RuntimeConfig, paths: RuntimePaths) -> Path:
    """
    Determine the correct MongoDB binary to use.

    Priority:
    1. Explicit binary path provided in RuntimeConfig
    2. Bundled runtime binary based on OS
    """

    # If user explicitly supplied a binary path, use it
    if cfg.mongo_binary_path:
        binary = Path(cfg.mongo_binary_path).expanduser().resolve()

        if not binary.exists():
            raise FileNotFoundError(f"Specified Mongo binary not found: {binary}")

        return binary

    system = platform.system()

    if system == "Windows":
        binary = paths.runtime_binaries_dir / "windows" / "mongod.exe"

    elif system == "Darwin":
        binary = paths.runtime_binaries_dir / "macos" / "mongod"

    elif system == "Linux":
        binary = paths.runtime_binaries_dir / "linux" / "mongod"

    else:
        raise RuntimeError(f"Unsupported operating system: {system}")

    if not binary.exists():
        raise FileNotFoundError(
            f"Mongo binary not found for {system}. Expected at: {binary}"
        )

    return binary.resolve()