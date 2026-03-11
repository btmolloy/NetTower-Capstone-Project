# Purpose: Parse launch-time inputs (CLI / env) and produce a RuntimeConfig
# used by the supervisor to bootstrap NetTower.
# Inputs: CLI args and environment variables.
# Outputs: A validated RuntimeConfig instance.

from __future__ import annotations

import argparse
import os

from backEnd.runtime.config import RuntimeConfig
from backEnd.utils.logging import get_logger


def _env_str(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()

    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    return default


def load_runtime_config() -> RuntimeConfig:
    """
    Build a RuntimeConfig using:
      - defaults
      - environment overrides
      - CLI overrides
    """

    parser = argparse.ArgumentParser(prog="nettower", add_help=True)

    # Logging
    parser.add_argument("--log-level", dest="log_level", help="log level (INFO, DEBUG, etc)")
    parser.add_argument("--log-file", dest="log_file", help="log file path")

    # Mongo connection
    parser.add_argument("--mongo-uri", dest="mongo_uri", help="mongodb uri")
    parser.add_argument("--mongo-db", dest="mongo_db_name", help="mongodb database name")

    # Mongo runtime
    parser.add_argument("--mongo-host", dest="mongo_host", help="mongo host")
    parser.add_argument("--mongo-port", dest="mongo_port", type=int, help="mongo port")
    parser.add_argument("--mongo-data-dir", dest="mongo_data_dir", help="mongo data directory")
    parser.add_argument("--mongo-log-path", dest="mongo_log_path", help="mongo log path")
    parser.add_argument("--mongo-binary", dest="mongo_binary_path", help="path to mongod binary")

    # Feature flags
    parser.add_argument("--no-mongo-auto-start", dest="mongo_auto_start", action="store_false")
    parser.add_argument("--launch-frontend", dest="launch_frontend", action="store_true")

    parser.set_defaults(
        mongo_auto_start=True,
        launch_frontend=False,
    )

    args = parser.parse_args()

    # Environment fallback
    cfg = RuntimeConfig(
        log_level=args.log_level or _env_str("NETTOWER_LOG_LEVEL", "INFO"),
        log_file=args.log_file or _env_str("NETTOWER_LOG_FILE"),

        mongo_uri=args.mongo_uri or _env_str("NETTOWER_MONGO_URI", "mongodb://127.0.0.1:27017"),
        mongo_db_name=args.mongo_db_name or _env_str("NETTOWER_MONGO_DB_NAME", "nettower"),

        mongo_host=args.mongo_host or _env_str("NETTOWER_MONGO_HOST", "127.0.0.1"),
        mongo_port=args.mongo_port or _env_int("NETTOWER_MONGO_PORT", 27017),

        mongo_data_dir=args.mongo_data_dir or _env_str("NETTOWER_MONGO_DATA_DIR", "runtime/mongo_data"),
        mongo_log_path=args.mongo_log_path or _env_str("NETTOWER_MONGO_LOG_PATH", "runtime/mongod.log"),
        mongo_binary_path=args.mongo_binary_path or _env_str("NETTOWER_MONGO_BINARY_PATH"),

        mongo_auto_start=bool(args.mongo_auto_start),
        launch_frontend=bool(args.launch_frontend),
    ).validate()

    log = get_logger("backEnd.runtime.settings", cfg.log_level, cfg.log_file)

    log.info(
        f"runtime config loaded: mongo_uri={cfg.mongo_uri} "
        f"mongo_host={cfg.mongo_host}:{cfg.mongo_port} "
        f"frontend={cfg.launch_frontend}"
    )

    return cfg