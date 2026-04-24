from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backEnd.processors.enrichment import enricher


class TestAutomatedEnrichment(unittest.TestCase):
    def setUp(self) -> None:
        self.e = enricher(SimpleNamespace(log_level="INFO"))

    def test_automated_07_vendor_based_role_hint_generation(self) -> None:
        role = self.e._role_hint(vendor="Cisco Systems", mac=None, hostname=None)
        self.assertEqual("network", role)

    def test_automated_08_hostname_keyword_role_hint_generation(self) -> None:
        role = self.e._role_hint(vendor=None, mac=None, hostname="office-printer-01")
        self.assertEqual("printer", role)

    def test_automated_09_operating_system_guess_from_open_ports(self) -> None:
        os_guess = self.e._os_guess_from_port(port=3389, state="open")
        self.assertEqual("Windows", os_guess)

    def test_automated_10_operating_system_guess_from_service_signatures(self) -> None:
        os_guess = self.e._os_guess_from_service(
            service="ssh",
            product="OpenSSH",
            version="9.3",
            extrainfo="Ubuntu Linux",
        )
        self.assertEqual("Linux", os_guess)


if __name__ == "__main__":
    unittest.main()
