# Purpose: Maintain mutable runtime session state for NetTower.
# Inputs: Initial SessionConfig and runtime update requests.
# Outputs: Thread-safe access to current scan session parameters.

from __future__ import annotations

from threading import Lock
from typing import Optional

from backEnd.runtime.session_config import SessionConfig


class SessionManager:
    """
    Holds mutable runtime session settings.

    These values may be updated while the backend loop is running
    (except interface, which requires restart).
    """

    def __init__(self, session_cfg: SessionConfig) -> None:
        self._lock = Lock()

        # immutable during session
        self._interface: Optional[str] = session_cfg.interface

        # mutable runtime values
        self._enable_passive_listener: bool = session_cfg.enable_passive_listener
        self._enable_active_discovery: bool = session_cfg.enable_active_discovery
        self._discovery_interval_seconds: int = session_cfg.discovery_interval_seconds
        self._targeted_scan_cooldown_seconds: int = session_cfg.targeted_scan_cooldown_seconds
        self._discovery_target_cidr: Optional[str] = session_cfg.discovery_target_cidr

    # ---------------------------------------------------------
    # Getters
    # ---------------------------------------------------------

    def get_interface(self) -> Optional[str]:
        return self._interface

    def get_enable_passive_listener(self) -> bool:
        with self._lock:
            return self._enable_passive_listener

    def get_enable_active_discovery(self) -> bool:
        with self._lock:
            return self._enable_active_discovery

    def get_discovery_interval_seconds(self) -> int:
        with self._lock:
            return self._discovery_interval_seconds

    def get_targeted_scan_cooldown_seconds(self) -> int:
        with self._lock:
            return self._targeted_scan_cooldown_seconds

    def get_discovery_target_cidr(self) -> Optional[str]:
        with self._lock:
            return self._discovery_target_cidr

    # ---------------------------------------------------------
    # Setters (runtime updates)
    # ---------------------------------------------------------

    def set_enable_passive_listener(self, value: bool) -> None:
        with self._lock:
            self._enable_passive_listener = bool(value)

    def set_enable_active_discovery(self, value: bool) -> None:
        with self._lock:
            self._enable_active_discovery = bool(value)

    def set_discovery_interval_seconds(self, value: int) -> None:
        if value <= 0:
            raise ValueError("discovery_interval_seconds must be > 0")

        with self._lock:
            self._discovery_interval_seconds = int(value)

    def set_targeted_scan_cooldown_seconds(self, value: int) -> None:
        if value < 0:
            raise ValueError("targeted_scan_cooldown_seconds must be >= 0")

        with self._lock:
            self._targeted_scan_cooldown_seconds = int(value)

    def set_discovery_target_cidr(self, value: Optional[str]) -> None:
        with self._lock:
            if value:
                value = value.strip()
                if value == "":
                    value = None
            self._discovery_target_cidr = value

    # ---------------------------------------------------------
    # Snapshot (optional convenience)
    # ---------------------------------------------------------

    def snapshot(self) -> dict:
        """
        Return a snapshot of current session state.
        Useful for APIs or UI queries.
        """
        with self._lock:
            return {
                "interface": self._interface,
                "enable_passive_listener": self._enable_passive_listener,
                "enable_active_discovery": self._enable_active_discovery,
                "discovery_interval_seconds": self._discovery_interval_seconds,
                "targeted_scan_cooldown_seconds": self._targeted_scan_cooldown_seconds,
                "discovery_target_cidr": self._discovery_target_cidr,
            }