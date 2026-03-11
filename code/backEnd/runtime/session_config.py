# Purpose: Define the user-selected scan session configuration for a NetTower run.
# Inputs: Values selected by the user in the frontend startup/control window.
# Outputs: A validated SessionConfig object used by the backend runtime when a scan session starts.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionConfig:
    """
    User-selected runtime session configuration for NetTower.

    This config is created after the user selects scan options and presses
    Start in the frontend. It contains scan/session behavior only and must
    not contain bootstrap/runtime-environment settings such as Mongo binary
    paths, runtime directories, or process-launch controls.
    """

    # Sensor toggles
    enable_passive_listener: bool = True
    enable_active_discovery: bool = False

    # Network selection
    interface: str | None = None
    discovery_target_cidr: str | None = None

    # Discovery behavior
    discovery_interval_seconds: int = 120
    targeted_scan_cooldown_seconds: int = 300

    def validate(self) -> "SessionConfig":
        """
        Return a validated/normalized copy of the session config.

        This method performs only local validation and normalization.
        It must not perform interface detection, CIDR discovery, filesystem
        access, process control, or any other startup/runtime side effects.
        """

        interface = self.interface.strip() if isinstance(self.interface, str) else self.interface
        if interface == "":
            interface = None

        discovery_target_cidr = (
            self.discovery_target_cidr.strip()
            if isinstance(self.discovery_target_cidr, str)
            else self.discovery_target_cidr
        )
        if discovery_target_cidr == "":
            discovery_target_cidr = None

        discovery_interval_seconds = max(1, int(self.discovery_interval_seconds))
        targeted_scan_cooldown_seconds = max(0, int(self.targeted_scan_cooldown_seconds))

        return SessionConfig(
            enable_passive_listener=bool(self.enable_passive_listener),
            enable_active_discovery=bool(self.enable_active_discovery),
            interface=interface,
            discovery_target_cidr=discovery_target_cidr,
            discovery_interval_seconds=discovery_interval_seconds,
            targeted_scan_cooldown_seconds=targeted_scan_cooldown_seconds,
        )
    def to_dict(self) -> dict:
        return {
            "enable_passive_listener": self.enable_passive_listener,
            "enable_active_discovery": self.enable_active_discovery,
            "interface": self.interface,
            "discovery_target_cidr": self.discovery_target_cidr,
            "discovery_interval_seconds": self.discovery_interval_seconds,
            "targeted_scan_cooldown_seconds": self.targeted_scan_cooldown_seconds,
        }


    @staticmethod
    def from_dict(data: dict) -> "SessionConfig":
        return SessionConfig(
            enable_passive_listener=bool(data.get("enable_passive_listener", True)),
            enable_active_discovery=bool(data.get("enable_active_discovery", False)),
            interface=data.get("interface"),
            discovery_target_cidr=data.get("discovery_target_cidr"),
            discovery_interval_seconds=int(data.get("discovery_interval_seconds", 120)),
            targeted_scan_cooldown_seconds=int(data.get("targeted_scan_cooldown_seconds", 300)),
        )