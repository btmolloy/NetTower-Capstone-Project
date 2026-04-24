from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backEnd.models.events import host_seen, traffic_seen
from backEnd.models.types import protocol
from backEnd.processors.correlation import correlator
from backEnd.processors.enrichment import enricher
from backEnd.processors.extractors import extractor
from helpers import InMemoryLibrarian, apply_updates, make_meta


class TestAutomatedExtractorPipelineSnapshot(unittest.TestCase):
    def test_automated_19_event_extraction_from_canonical_event_object(self) -> None:
        ext = extractor()
        event = host_seen(meta=make_meta(), ip="192.168.1.22", mac="aa:bb:cc:dd:ee:01")

        events = ext.to_events(event)
        self.assertEqual(1, len(events))
        self.assertIs(event, events[0])

    def test_automated_20_event_extraction_from_raw_dictionary_payload(self) -> None:
        ext = extractor()
        payload = {
            "type": "traffic_seen",
            "meta": {
                "source": "TCPDUMP",
                "iface": "en0",
                "confidence": "MEDIUM",
            },
            "src_ip": "192.168.1.22",
            "dst_ip": "192.168.1.33",
            "proto": "UDP",
            "src_port": 12345,
            "dst_port": 53,
            "bytes": 64,
        }

        events = ext.to_events(payload)
        self.assertEqual(1, len(events))
        self.assertIsInstance(events[0], traffic_seen)
        self.assertEqual(protocol.udp, events[0].proto)
        self.assertEqual(12345, events[0].src_port)
        self.assertEqual(53, events[0].dst_port)

    def test_automated_21_end_to_end_flow_from_event_to_stored_topology_updates(self) -> None:
        store = InMemoryLibrarian()
        ext = extractor()
        enr = enricher(SimpleNamespace(log_level="INFO"))
        corr = correlator(store)

        raw_events = [
            {
                "type": "host_seen",
                "meta": {"source": "TCPDUMP", "iface": "en0", "confidence": "HIGH"},
                "ip": "192.168.1.22",
                "mac": "aa:bb:cc:dd:ee:01",
                "hostname": "host-one",
            },
            {
                "type": "host_seen",
                "meta": {"source": "TCPDUMP", "iface": "en0", "confidence": "HIGH"},
                "ip": "192.168.1.33",
                "mac": "aa:bb:cc:dd:ee:02",
                "hostname": "host-two",
            },
            {
                "type": "traffic_seen",
                "meta": {"source": "TCPDUMP", "iface": "en0", "confidence": "MEDIUM"},
                "src_ip": "192.168.1.22",
                "dst_ip": "192.168.1.33",
                "proto": "TCP",
                "src_port": 53111,
                "dst_port": 443,
                "bytes": 512,
            },
        ]

        for raw in raw_events:
            events = ext.to_events(raw)
            self.assertEqual(1, len(events))
            event = events[0]
            event, enrichment_data = enr.enrich(event)
            host_updates, edge_updates, _signals = corr.process(event, enrichment_data)
            apply_updates(store, host_updates, edge_updates)

        self.assertGreaterEqual(store.host_count(), 2)
        self.assertGreaterEqual(store.edge_count(), 1)
        only_edge = next(iter(store.edges_by_key.values()))
        self.assertGreaterEqual(only_edge.count, 1)
        self.assertTrue(bool(only_edge.relationship_type))

    def test_automated_22_topology_snapshot_response_structure_and_record_limits(self) -> None:
        module_path = ROOT / "frontEnd" / "supervisor_bridge.py"
        spec = importlib.util.spec_from_file_location("frontend_supervisor_bridge_for_tests", module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        class FakeSupervisor:
            def __init__(self, running: bool = True) -> None:
                self._running = running

            def is_running(self) -> bool:
                return self._running

        captured: dict[str, int] = {}

        def fake_get_topology_snapshot(_runtime_cfg, limit_hosts: int, limit_edges: int) -> dict:
            captured["limit_hosts"] = limit_hosts
            captured["limit_edges"] = limit_edges
            return {
                "hosts": [{"host_id": "h1"}],
                "edges": [{"edge_key": "e1"}],
                "captured_at": "2026-04-24T00:00:00Z",
            }

        module.get_topology_snapshot = fake_get_topology_snapshot

        runtime_cfg = module.RuntimeConfig().validate()
        ok, result = module.handle_command(
            FakeSupervisor(running=True),
            runtime_cfg,
            "get_topology_snapshot",
            {
                "limit_hosts": 5,
                "limit_edges": 9000,
            },
        )

        self.assertTrue(ok)
        self.assertEqual(10, captured.get("limit_hosts"))
        self.assertEqual(4000, captured.get("limit_edges"))
        self.assertIn("hosts", result)
        self.assertIn("edges", result)
        self.assertIn("captured_at", result)
        self.assertIn("running", result)
        self.assertTrue(result["running"])


if __name__ == "__main__":
    unittest.main()
