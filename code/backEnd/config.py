# Purpose: Define the application configuration structure and defaults
# (Mongo URI, interface, scan targets, intervals, toggles).
# Inputs: Defaults + values provided by settings/CLI/env.
# Outputs: A validated Config object used by main, sensors, and storage.

from __future__ import annotations

from dataclasses import dataclass, replace
import os

from backEnd.utils.net import detect_capture_interface


def _env_str(*names: str, default: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip() != "":
            return value.strip()
    return default


def _env_int(*names: str, default: int) -> int:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip() != "":
            try:
                return int(value.strip())
            except ValueError:
                return default
    return default


def _env_bool(*names: str, default: bool) -> bool:
    truthy = {"1", "true", "yes", "on"}
    falsy = {"0", "false", "no", "off"}

    for name in names:
        value = os.getenv(name)
        if value is None:
            continue

        normalized = value.strip().lower()
        if normalized in truthy:
            return True
        if normalized in falsy:
            return False

    return default


@dataclass(frozen=True)
class config:
    """
    Central application configuration.
    Immutable once created.
    """

    # Logging
    log_level: str = "INFO"
    log_file: str | None = None

    # Network interface
    interface: str | None = None

    # Discovery scheduling
    discovery_interval_seconds: int = 120
    targeted_scan_cooldown_seconds: int = 300

    # Discovery target
    discovery_target_cidr: str | None = None

    # MongoDB connection target used by pymongo
    mongo_uri: str = "mongodb://127.0.0.1:27017"
    mongo_db_name: str = "nettower"

    # Local Mongo runtime management
    mongo_auto_start: bool = True
    mongo_host: str = "127.0.0.1"
    mongo_port: int = 27017
    mongo_data_dir: str = "runtime/mongo_data"
    mongo_log_path: str | None = "runtime/mongod.log"
    mongo_reset_on_launch: bool = True
    mongo_delete_on_shutdown: bool = True
    mongo_startup_timeout_seconds: int = 20
    mongo_binary_path: str | None = None

    # Feature toggles
    enable_passive_listener: bool = True
    enable_active_discovery: bool = False

    @staticmethod
    def from_env() -> "config":
        """
        Create config from environment variables.
        Supports both legacy and newer env var names.
        """

        mongo_host = _env_str("NETTOWER_MONGO_HOST", default="127.0.0.1")
        mongo_port = _env_int("NETTOWER_MONGO_PORT", default=27017)

        cfg = config(
            log_level=_env_str("NETTOWER_LOG_LEVEL", default="INFO"),
            log_file=os.getenv("NETTOWER_LOG_FILE") or None,

            interface=_env_str("NETTOWER_INTERFACE", default="") or None,

            discovery_interval_seconds=_env_int(
                "NETTOWER_DISCOVERY_INTERVAL",
                default=20,
            ),
            targeted_scan_cooldown_seconds=_env_int(
                "NETTOWER_TARGETED_COOLDOWN",
                "NETTOWER_TARGETED_SCAN_COOLDOWN_SECONDS",
                default=20,
            ),

            discovery_target_cidr=_env_str(
                "NETTOWER_DISCOVERY_TARGET_CIDR",
                "NETTOWER_DISCOVERY_CIDR",
                default="",
            ) or None,

            mongo_uri=_env_str(
                "NETTOWER_MONGO_URI",
                default=f"mongodb://{mongo_host}:{mongo_port}",
            ),
            mongo_db_name=_env_str(
                "NETTOWER_MONGO_DB_NAME",
                "NETTOWER_MONGO_DB",
                default="nettower",
            ),

            mongo_auto_start=_env_bool(
                "NETTOWER_MONGO_AUTO_START",
                default=True,
            ),
            mongo_host=mongo_host,
            mongo_port=mongo_port,
            mongo_data_dir=_env_str(
                "NETTOWER_MONGO_DATA_DIR",
                default="runtime/mongo_data",
            ),
            mongo_log_path=_env_str(
                "NETTOWER_MONGO_LOG_PATH",
                default="runtime/mongod.log",
            ) or None,
            mongo_reset_on_launch=_env_bool(
                "NETTOWER_MONGO_RESET_ON_LAUNCH",
                default=True,
            ),
            mongo_delete_on_shutdown=_env_bool(
                "NETTOWER_MONGO_DELETE_ON_SHUTDOWN",
                default=True,
            ),
            mongo_startup_timeout_seconds=_env_int(
                "NETTOWER_MONGO_STARTUP_TIMEOUT_SECONDS",
                default=20,
            ),
            mongo_binary_path=_env_str(
                "NETTOWER_MONGO_BINARY_PATH",
                default="",
            ) or None,

            enable_passive_listener=_env_bool(
                "NETTOWER_ENABLE_PASSIVE_LISTENER",
                "NETTOWER_ENABLE_PASSIVE",
                default=True,
            ),
            enable_active_discovery=_env_bool(
                "NETTOWER_ENABLE_ACTIVE_DISCOVERY",
                "NETTOWER_ENABLE_ACTIVE",
                default=False,
            ),
        )

        if not cfg.interface:
            detected = detect_capture_interface()
            cfg = replace(cfg, interface=detected)

        return cfg