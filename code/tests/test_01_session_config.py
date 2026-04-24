from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backEnd.runtime.session_config import SessionConfig


class TestAutomatedSessionConfig(unittest.TestCase):
    def test_automated_01_empty_interface_normalizes_to_none(self) -> None:
        cfg = SessionConfig(interface="   ")
        validated = cfg.validate()
        self.assertIsNone(validated.interface)

    def test_automated_02_empty_discovery_target_normalizes_to_none(self) -> None:
        cfg = SessionConfig(discovery_target_cidr="   ")
        validated = cfg.validate()
        self.assertIsNone(validated.discovery_target_cidr)

    def test_automated_03_discovery_interval_is_clamped_to_minimum_one(self) -> None:
        cfg = SessionConfig(discovery_interval_seconds=0)
        validated = cfg.validate()
        self.assertEqual(1, validated.discovery_interval_seconds)

    def test_automated_04_targeted_cooldown_is_clamped_to_non_negative(self) -> None:
        cfg = SessionConfig(targeted_scan_cooldown_seconds=-50)
        validated = cfg.validate()
        self.assertEqual(0, validated.targeted_scan_cooldown_seconds)

    def test_automated_05_valid_values_are_preserved(self) -> None:
        cfg = SessionConfig(
            interface="en0",
            discovery_target_cidr="192.168.1.0/24",
            enable_passive_listener=True,
            enable_active_discovery=True,
            allow_all_active_targets=False,
            enable_icmp_scan=True,
            enable_nmap_scan=False,
            discovery_interval_seconds=120,
            targeted_scan_cooldown_seconds=300,
        )
        validated = cfg.validate()
        self.assertEqual("en0", validated.interface)
        self.assertEqual("192.168.1.0/24", validated.discovery_target_cidr)
        self.assertTrue(validated.enable_active_discovery)
        self.assertFalse(validated.enable_nmap_scan)
        self.assertEqual(120, validated.discovery_interval_seconds)
        self.assertEqual(300, validated.targeted_scan_cooldown_seconds)

    def test_automated_06_boolean_fields_are_coerced(self) -> None:
        cfg = SessionConfig(
            enable_passive_listener=1,  # type: ignore[arg-type]
            enable_active_discovery="yes",  # type: ignore[arg-type]
            allow_all_active_targets="",  # type: ignore[arg-type]
            enable_icmp_scan=0,  # type: ignore[arg-type]
            enable_nmap_scan=1,  # type: ignore[arg-type]
        )
        validated = cfg.validate()
        self.assertTrue(validated.enable_passive_listener)
        self.assertTrue(validated.enable_active_discovery)
        self.assertFalse(validated.allow_all_active_targets)
        self.assertFalse(validated.enable_icmp_scan)
        self.assertTrue(validated.enable_nmap_scan)


if __name__ == "__main__":
    unittest.main()
