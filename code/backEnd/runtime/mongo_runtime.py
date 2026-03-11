# Purpose: Manage the lifecycle of the embedded MongoDB process used by NetTower.
# Inputs: RuntimeConfig, RuntimePaths, and resolved mongod binary path.
# Outputs: Running mongod process bound to the configured host/port.

from __future__ import annotations

import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional

from backEnd.runtime.config import RuntimeConfig
from backEnd.runtime.paths import RuntimePaths
from backEnd.utils.logging import get_logger


class MongoRuntimeManager:
    """
    Manages a local throwaway mongod process for NetTower.

    Behavior:
    - optionally wipes the Mongo data directory before startup
    - starts mongod bound to cfg.mongo_host:cfg.mongo_port
    - waits until the port is accepting connections
    - stops mongod on shutdown
    - optionally deletes the Mongo data directory on shutdown
    """

    def __init__(
        self,
        cfg: RuntimeConfig,
        paths: RuntimePaths,
        mongod_binary: Path,
    ) -> None:
        self._cfg = cfg
        self._paths = paths
        self._mongod_binary = mongod_binary

        self._log = get_logger(
            "backEnd.runtime.mongo_runtime",
            cfg.log_level,
            cfg.log_file,
        )

        self._proc: Optional[subprocess.Popen[str]] = None

    def start(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return

        data_dir = self._paths.mongo_data_dir
        log_path = self._paths.mongo_log_path

        if self._cfg.mongo_reset_on_launch and data_dir.exists():
            self._log.info(f"Removing previous Mongo data dir: {data_dir}")
            shutil.rmtree(data_dir, ignore_errors=True)

        data_dir.mkdir(parents=True, exist_ok=True)

        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(self._mongod_binary),
            "--dbpath",
            str(data_dir),
            "--bind_ip",
            str(self._cfg.mongo_host),
            "--port",
            str(self._cfg.mongo_port),
        ]

        if log_path is not None:
            cmd.extend(["--logpath", str(log_path), "--logappend"])

        self._log.info(
            f"Starting local mongod: "
            f"host={self._cfg.mongo_host} "
            f"port={self._cfg.mongo_port} "
            f"dbpath={data_dir} "
            f"binary={self._mongod_binary}"
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

        if self._cfg.mongo_delete_on_shutdown:
            data_dir = self._paths.mongo_data_dir
            if data_dir.exists():
                self._log.info(f"Deleting Mongo data dir: {data_dir}")
                shutil.rmtree(data_dir, ignore_errors=True)

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