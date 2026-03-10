from __future__ import annotations

import platform
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from backEnd.utils.logging import get_logger


class mongo_runtime_manager:
    """
    Manages a local throwaway mongod process for NetTower.

    Behavior:
    - optionally wipes the Mongo data directory before startup
    - starts mongod bound to cfg.mongo_host:cfg.mongo_port
    - waits until the port is accepting connections
    - stops mongod on shutdown
    - optionally deletes the Mongo data directory on shutdown

    mongod resolution order:
    1. cfg.mongo_binary_path
    2. bundled runtime binary shipped with NetTower
    3. PATH lookup (shutil.which)
    """

    def __init__(self, cfg: Any) -> None:
        self._cfg = cfg
        self._log = get_logger(
            "backEnd.storage.mongo_runtime",
            getattr(cfg, "log_level", "INFO"),
            getattr(cfg, "log_file", None),
        )
        self._proc: Optional[subprocess.Popen[str]] = None

    def start(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return

        mongod_path = self._resolve_mongod_path()

        data_dir = Path(self._cfg.mongo_data_dir).resolve()
        log_path = Path(self._cfg.mongo_log_path).resolve() if self._cfg.mongo_log_path else None

        if getattr(self._cfg, "mongo_reset_on_launch", True) and data_dir.exists():
            self._log.info(f"Removing previous Mongo data dir: {data_dir}")
            shutil.rmtree(data_dir, ignore_errors=True)

        data_dir.mkdir(parents=True, exist_ok=True)

        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            mongod_path,
            "--dbpath", str(data_dir),
            "--bind_ip", str(self._cfg.mongo_host),
            "--port", str(self._cfg.mongo_port),
        ]

        if log_path is not None:
            cmd.extend(["--logpath", str(log_path), "--logappend"])

        self._log.info(
            f"Starting local mongod: host={self._cfg.mongo_host} "
            f"port={self._cfg.mongo_port} dbpath={data_dir} binary={mongod_path}"
        )

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except Exception as exc:
            raise RuntimeError(f"failed to start mongod: {exc}") from exc

        try:
            self._wait_until_ready(
                host=str(self._cfg.mongo_host),
                port=int(self._cfg.mongo_port),
                timeout_seconds=int(self._cfg.mongo_startup_timeout_seconds),
            )
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        proc = self._proc
        self._proc = None

        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5.0)
                    except Exception:
                        proc.kill()
                        proc.wait(timeout=2.0)
            except Exception:
                pass

        if getattr(self._cfg, "mongo_delete_on_shutdown", True):
            data_dir = Path(self._cfg.mongo_data_dir).resolve()
            if data_dir.exists():
                self._log.info(f"Deleting Mongo data dir: {data_dir}")
                shutil.rmtree(data_dir, ignore_errors=True)

    def _resolve_mongod_path(self) -> str:
        configured = getattr(self._cfg, "mongo_binary_path", None)
        if configured:
            configured_path = Path(configured).expanduser().resolve()
            if configured_path.exists() and configured_path.is_file():
                return str(configured_path)
            raise RuntimeError(f"configured mongod binary not found: {configured_path}")

        bundled = self._get_bundled_mongod_path()
        if bundled is not None:
            return bundled

        discovered = shutil.which("mongod")
        if discovered:
            return discovered

        raise RuntimeError(
            "mongod not found. Set NETTOWER_MONGO_BINARY_PATH, bundle mongod with the app, or install MongoDB."
        )

    def _get_bundled_mongod_path(self) -> str | None:
        """
        Look for a NetTower-bundled mongod binary relative to the project/app root.

        Expected layout:
            code/
              runtime_binaries/
                windows/mongod.exe
                linux/mongod
                macos/mongod
        """
        project_root = self._get_project_root()
        system = platform.system().lower()

        if system == "windows":
            candidate = project_root / "runtime_binaries" / "windows" / "mongod.exe"
        elif system == "darwin":
            candidate = project_root / "runtime_binaries" / "macos" / "mongod"
        else:
            candidate = project_root / "runtime_binaries" / "linux" / "mongod"

        if candidate.exists() and candidate.is_file():
            return str(candidate.resolve())

        return None

    def _get_project_root(self) -> Path:
        """
        Resolve the NetTower code/ directory from this file location.

        Current file:
            code/backEnd/storage/mongo_runtime.py

        Project root returned:
            code/
        """
        return Path(__file__).resolve().parents[2]

    def _wait_until_ready(self, host: str, port: int, timeout_seconds: int) -> None:
        deadline = time.time() + max(1, timeout_seconds)

        while time.time() < deadline:
            if self._proc is not None and self._proc.poll() is not None:
                raise RuntimeError("mongod exited before becoming ready")

            try:
                with socket.create_connection((host, port), timeout=1.0):
                    self._log.info(f"mongod is ready on {host}:{port}")
                    return
            except OSError:
                time.sleep(0.25)

        raise RuntimeError(f"timed out waiting for mongod on {host}:{port}")