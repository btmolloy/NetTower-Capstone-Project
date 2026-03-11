# Purpose: Define bootstrap/runtime configuration structure and defaults.
# Inputs: Resolved values from runtime/settings.py and runtime/paths.py.
# Outputs: A validated RuntimeConfig object used by the supervisor and bootstrap layer.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeConfig:
    """
    Bootstrap/runtime configuration for NetTower.

    This config is only for launch-time infrastructure concerns such as
    logging, runtime paths, and embedded MongoDB lifecycle settings.

    It must not contain user-selected scan session settings such as
    interface choice, sensor toggles, scan intervals, or discovery targets.
    """

    # Logging
    log_level: str = "INFO"
    log_file: str | None = None

    # Mongo connection settings
    mongo_uri: str = "mongodb://127.0.0.1:27017"
    mongo_db_name: str = "nettower"

    # Embedded Mongo runtime settings
    mongo_auto_start: bool = True
    mongo_host: str = "127.0.0.1"
    mongo_port: int = 27017
    mongo_data_dir: str = "runtime/mongo_data"
    mongo_log_path: str | None = "runtime/mongod.log"
    mongo_reset_on_launch: bool = True
    mongo_delete_on_shutdown: bool = True
    mongo_startup_timeout_seconds: int = 20
    mongo_binary_path: str | None = None

    # Optional frontend launch control
    launch_frontend: bool = False

    def validate(self) -> "RuntimeConfig":
        """
        Return a validated/normalized copy of the config.

        This method performs only local validation and normalization.
        It must not perform any filesystem, process, or network side effects.
        """

        log_level = (self.log_level or "INFO").strip().upper()
        if not log_level:
            log_level = "INFO"

        log_file = self.log_file.strip() if isinstance(self.log_file, str) else self.log_file
        if log_file == "":
            log_file = None

        mongo_host = (self.mongo_host or "127.0.0.1").strip() or "127.0.0.1"
        mongo_port = max(1, min(65535, int(self.mongo_port)))
        mongo_db_name = (self.mongo_db_name or "nettower").strip() or "nettower"
        mongo_startup_timeout_seconds = max(1, int(self.mongo_startup_timeout_seconds))

        mongo_data_dir = (
            self.mongo_data_dir.strip()
            if isinstance(self.mongo_data_dir, str)
            else self.mongo_data_dir
        )

        mongo_log_path = (
            self.mongo_log_path.strip()
            if isinstance(self.mongo_log_path, str)
            else self.mongo_log_path
        )
        if mongo_log_path == "":
            mongo_log_path = None

        mongo_binary_path = (
            self.mongo_binary_path.strip()
            if isinstance(self.mongo_binary_path, str)
            else self.mongo_binary_path
        )
        if mongo_binary_path == "":
            mongo_binary_path = None

        mongo_uri = (self.mongo_uri or "").strip()
        if not mongo_uri:
            mongo_uri = f"mongodb://{mongo_host}:{mongo_port}"

        return RuntimeConfig(
            log_level=log_level,
            log_file=log_file,
            mongo_uri=mongo_uri,
            mongo_db_name=mongo_db_name,
            mongo_auto_start=bool(self.mongo_auto_start),
            mongo_host=mongo_host,
            mongo_port=mongo_port,
            mongo_data_dir=mongo_data_dir,
            mongo_log_path=mongo_log_path,
            mongo_reset_on_launch=bool(self.mongo_reset_on_launch),
            mongo_delete_on_shutdown=bool(self.mongo_delete_on_shutdown),
            mongo_startup_timeout_seconds=mongo_startup_timeout_seconds,
            mongo_binary_path=mongo_binary_path,
            launch_frontend=bool(self.launch_frontend),
        )