from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backEnd.models.events import host_seen, route_hop_seen, traffic_seen
from backEnd.processors.correlation import correlator
from backEnd.processors.extractors import extractor
from backEnd.runtime.config import RuntimeConfig
from helpers import InMemoryLibrarian, apply_updates, make_meta


class TestAutomatedRuntimeAndIntegration(unittest.TestCase):
    def test_automated_23_runtime_config_generates_default_mongo_uri_when_blank(self) -> None:
        cfg = RuntimeConfig(mongo_uri="", mongo_host="10.20.30.40", mongo_port=70000)
        validated = cfg.validate()
        self.assertEqual(65535, validated.mongo_port)
        self.assertEqual("mongodb://10.20.30.40:65535", validated.mongo_uri)

    def test_automated_24_runtime_config_normalizes_log_and_optional_paths(self) -> None:
        cfg = RuntimeConfig(
            log_level=" debug ",
            log_file="   ",
            mongo_log_path="",
            mongo_binary_path="",
        )
        validated = cfg.validate()
        self.assertEqual("DEBUG", validated.log_level)
        self.assertIsNone(validated.log_file)
        self.assertIsNone(validated.mongo_log_path)
        self.assertIsNone(validated.mongo_binary_path)

    def test_automated_25_extractor_returns_empty_list_for_payload_without_valid_meta(self) -> None:
        ext = extractor()
        raw_payload = {
            "type": "host_seen",
            "ip": "192.168.1.55",
            "mac": "aa:bb:cc:dd:ee:55",
        }
        self.assertEqual([], ext.to_events(raw_payload))

    def test_automated_26_new_host_seen_emits_targeted_scan_signal(self) -> None:
        store = InMemoryLibrarian()
        corr = correlator(store)

        event = host_seen(meta=make_meta(), ip="192.168.1.77", mac="aa:bb:cc:dd:ee:77")
        host_updates, edge_updates, signals = corr.process(event, enrichment_data={})
        apply_updates(store, host_updates, edge_updates)

        self.assertTrue(signals.new_host_detected)
        self.assertEqual("192.168.1.77", signals.targeted_scan_ip)
        self.assertEqual(1, store.host_count())
        self.assertEqual(0, store.edge_count())

    def test_automated_27_traffic_to_unknown_destination_does_not_create_edge(self) -> None:
        store = InMemoryLibrarian()
        corr = correlator(store)

        seed_event = host_seen(meta=make_meta(), ip="192.168.1.90", mac="aa:bb:cc:dd:ee:90")
        host_updates, edge_updates, _ = corr.process(seed_event, enrichment_data={})
        apply_updates(store, host_updates, edge_updates)

        traffic_event = traffic_seen(
            meta=make_meta(),
            src_ip="192.168.1.90",
            dst_ip="192.168.1.250",
        )
        host_updates, edge_updates, signals = corr.process(traffic_event, enrichment_data={})
        apply_updates(store, host_updates, edge_updates)

        self.assertFalse(signals.new_edge_detected)
        self.assertEqual(0, len(edge_updates))
        self.assertEqual(1, store.host_count())
        self.assertEqual(0, store.edge_count())

    def test_automated_28_route_hop_creates_relationship_and_parent_hint(self) -> None:
        store = InMemoryLibrarian()
        corr = correlator(store)

        hop_event = route_hop_seen(
            meta=make_meta(),
            target_ip="192.168.2.20",
            hop_ip="192.168.1.1",
            hop_index=1,
        )
        host_updates, edge_updates, signals = corr.process(hop_event, enrichment_data={})
        apply_updates(store, host_updates, edge_updates)

        self.assertEqual(2, len(host_updates))
        self.assertEqual(1, len(edge_updates))
        self.assertTrue(signals.new_edge_detected)

        target_host = next(host for host in host_updates if "192.168.2.20" in host.ips)
        hop_host = next(host for host in host_updates if "192.168.1.1" in host.ips)
        edge = edge_updates[0]

        self.assertEqual(hop_host.host_id, target_host.parent_candidate)
        self.assertEqual(2, target_host.topology_layer)
        self.assertEqual("gateway-for", edge.relationship_type)


if __name__ == "__main__":
    unittest.main()
