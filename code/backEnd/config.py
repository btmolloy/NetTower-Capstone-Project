#Purpose: Define the application configuration structure and defaults (Mongo URI, interface, scan targets, intervals, toggles).
#Inputs: Defaults + values provided by settings/CLI/env.
#Outputs: A validated Config object used by main, sensors, and storage.

from __future__ import annotations

from dataclasses import dataclass
import os


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
    interface: str = "eth0"

    # Discovery scheduling
    discovery_interval_seconds: int = 120
    targeted_scan_cooldown_seconds: int = 300

    # Discovery target
    discovery_target_cidr: str = "192.168.1.0/24"

    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "nettower"

    # Feature toggles
    enable_passive_listener: bool = True
    enable_active_discovery: bool = True

    @staticmethod
    def from_env() -> "config":
        """
        Create config from environment variables.
        Safe fallbacks for all fields.
        """

        return config(
            log_level=os.getenv("NETTOWER_LOG_LEVEL", "INFO"),
            log_file=os.getenv("NETTOWER_LOG_FILE") or None,
            interface=os.getenv("NETTOWER_INTERFACE", "eth0"),
            discovery_interval_seconds=int(
                os.getenv("NETTOWER_DISCOVERY_INTERVAL", "20")
            ),
            targeted_scan_cooldown_seconds=int(
                os.getenv("NETTOWER_TARGETED_COOLDOWN", "20")
            ),
            discovery_target_cidr=os.getenv(
                "NETTOWER_DISCOVERY_CIDR", "192.168.1.0/24"
            ),
            mongo_uri=os.getenv(
                "NETTOWER_MONGO_URI", "mongodb://localhost:27017"
            ),
            mongo_db_name=os.getenv(
                "NETTOWER_MONGO_DB", "nettower"
            ),
            enable_passive_listener=os.getenv(
                "NETTOWER_ENABLE_PASSIVE", "1"
            ) == "1",
            enable_active_discovery=os.getenv(
                "NETTOWER_ENABLE_ACTIVE", "1"
            ) == "1",
        )