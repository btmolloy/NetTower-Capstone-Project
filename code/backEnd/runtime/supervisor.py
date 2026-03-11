# Purpose: Manage NetTower runtime sessions.
# Inputs: RuntimeConfig (bootstrap settings) and SessionConfig (scan session settings).
# Outputs: Running Mongo + backend runtime when a session is started.

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from backEnd.runtime.binary_resolver import resolve_mongo_binary
from backEnd.runtime.config import RuntimeConfig
from backEnd.runtime.mongo_runtime import MongoRuntimeManager
from backEnd.runtime.paths import resolve_paths
from backEnd.runtime.runtime_state import clear_ready_flag, get_ready_flag, is_backend_ready
from backEnd.runtime.session_config import SessionConfig
from backEnd.runtime.shutdown import create_shutdown_flag, clear_shutdown_flag
from backEnd.utils.logging import get_logger


class Supervisor:
    """
    Controls NetTower runtime sessions.

    Responsibilities:
    - start Mongo runtime
    - start backend runtime
    - wait for backend readiness
    - stop both cleanly
    - allow multiple start/stop cycles during app lifetime
    """

    def __init__(self, runtime_cfg: RuntimeConfig) -> None:
        self._cfg = runtime_cfg

        self._log = get_logger(
            "backEnd.runtime.supervisor",
            runtime_cfg.log_level,
            runtime_cfg.log_file,
        )

        self._paths = resolve_paths(runtime_cfg)

        self._mongo_runtime: Optional[MongoRuntimeManager] = None
        self._backend_proc: Optional[subprocess.Popen] = None

        self._log.info("Supervisor initialized (idle state)")

    # ---------------------------------------------------------
    # Start runtime session
    # ---------------------------------------------------------

    def start_session(self, session_cfg: SessionConfig) -> None:
        """
        Start a NetTower scanning session.
        """

        if self._backend_proc and self._backend_proc.poll() is None:
            self._log.warning("Session already running")
            return

        self._log.info("Starting NetTower session")

        # Clear any stale runtime flags from a previous run/crash
        clear_ready_flag()
        clear_shutdown_flag()

        # Resolve Mongo binary
        mongod_binary = resolve_mongo_binary(self._cfg, self._paths)

        # Start Mongo
        if self._cfg.mongo_auto_start:
            self._mongo_runtime = MongoRuntimeManager(
                self._cfg,
                self._paths,
                mongod_binary,
            )
            self._mongo_runtime.start()

        # Write session config for backend startup
        session_file = self._paths.runtime_dir / "session_config.json"
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(session_cfg.to_dict(), f, indent=2)

        # Launch backend as a module from code root
        code_root = Path(__file__).resolve().parents[2]

        cmd = [
            sys.executable,
            "-m",
            "backEnd.main",
        ]

        self._log.info(f"Launching backend: {cmd}")

        try:
            self._backend_proc = subprocess.Popen(
                cmd,
                cwd=str(code_root),
            )
        except Exception as exc:
            self._log.error(f"Failed to start backend: {exc}")

            if self._mongo_runtime:
                self._mongo_runtime.stop()
                self._mongo_runtime = None

            raise

        # Wait for backend readiness
        self._wait_for_backend_ready()

    # ---------------------------------------------------------
    # Stop runtime session
    # ---------------------------------------------------------

    def stop_session(self) -> None:
        """
        Stop the running NetTower session.
        """

        self._log.info("Stopping NetTower session")

        # Request graceful backend shutdown
        if self._backend_proc:
            proc = self._backend_proc

            try:
                if proc.poll() is None:
                    self._log.info("Requesting graceful backend shutdown")
                    create_shutdown_flag()

                    try:
                        proc.wait(timeout=5)
                        self._log.info("Backend exited gracefully")
                    except subprocess.TimeoutExpired:
                        self._log.warning("Backend did not exit in time; terminating process")
                        proc.terminate()

                        try:
                            proc.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            self._log.warning("Backend did not terminate; killing process")
                            proc.kill()
                            proc.wait(timeout=2)
            except Exception as exc:
                self._log.warning(f"Error while stopping backend: {exc}")
            finally:
                self._backend_proc = None

        # Clear runtime flags after backend shutdown attempt
        clear_ready_flag()
        clear_shutdown_flag()

        # Stop Mongo
        if self._mongo_runtime:
            self._mongo_runtime.stop()
            self._mongo_runtime = None

        self._log.info("Session stopped")

    # ---------------------------------------------------------
    # Session state
    # ---------------------------------------------------------

    def is_running(self) -> bool:
        """
        Return True if a backend session is currently running.
        """

        return (
            self._backend_proc is not None
            and self._backend_proc.poll() is None
        )

    # ---------------------------------------------------------
    # Readiness
    # ---------------------------------------------------------

    def _wait_for_backend_ready(self) -> None:
        """
        Wait until the backend creates its ready flag or exits/fails.
        """

        timeout_seconds = 5.0
        poll_interval_seconds = 0.1
        deadline = time.time() + timeout_seconds

        ready_flag = get_ready_flag()

        while time.time() < deadline:
            if is_backend_ready():
                self._log.info(f"Backend ready: {ready_flag}")
                return

            if self._backend_proc is not None and self._backend_proc.poll() is not None:
                raise RuntimeError(
                    f"Backend exited before becoming ready. Ready flag was not created: {ready_flag}"
                )

            time.sleep(poll_interval_seconds)

        raise RuntimeError(
            f"Timed out waiting for backend ready flag: {ready_flag}"
        )