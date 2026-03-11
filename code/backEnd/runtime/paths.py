# Purpose: Resolve and prepare runtime filesystem paths used by NetTower.
# Inputs: RuntimeConfig values (which may contain relative paths).
# Outputs: Absolute paths for runtime directories and files.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backEnd.runtime.config import RuntimeConfig


@dataclass(frozen=True)
class RuntimePaths:
    """
    Resolved filesystem paths used by the runtime.
    All paths are absolute and platform-independent.
    """

    project_root: Path
    code_root: Path

    runtime_dir: Path
    mongo_data_dir: Path
    mongo_log_path: Path | None

    runtime_binaries_dir: Path


def resolve_paths(cfg: RuntimeConfig) -> RuntimePaths:
    """
    Convert relative paths from RuntimeConfig into absolute runtime paths.
    Also ensures required runtime directories exist.
    """

    # Locate project structure
    this_file = Path(__file__).resolve()

    # backEnd/runtime/paths.py -> backEnd -> code
    code_root = this_file.parents[2]
    project_root = code_root.parent

    runtime_dir = code_root / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    mongo_data_dir = runtime_dir / "mongo_data"
    mongo_data_dir.mkdir(parents=True, exist_ok=True)

    mongo_log_path = None
    if cfg.mongo_log_path:
        mongo_log_path = runtime_dir / Path(cfg.mongo_log_path).name
        mongo_log_path.parent.mkdir(parents=True, exist_ok=True)

    runtime_binaries_dir = code_root / "runtime_binaries"

    return RuntimePaths(
        project_root=project_root,
        code_root=code_root,
        runtime_dir=runtime_dir,
        mongo_data_dir=mongo_data_dir,
        mongo_log_path=mongo_log_path,
        runtime_binaries_dir=runtime_binaries_dir,
    )