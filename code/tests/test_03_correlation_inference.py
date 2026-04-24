from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backEnd.models.entities import host_entity
from backEnd.processors.correlation import correlator
from helpers import InMemoryLibrarian


class TestAutomatedCorrelationInference(unittest.TestCase):
    def test_automated_11_host_classification_into_node_classes(self) -> None:
        store = InMemoryLibrarian()
        corr = correlator(store)

        cases = [
            ("router", "router"),
            ("network", "switch"),
            ("server", "server"),
            ("workstation", "workstation"),
            ("other", "unknown"),
        ]

        for role, expected_node_role in cases:
            with self.subTest(role=role):
                host = host_entity(host_id=f"host_{role}")
                host.ips.add("192.168.1.50")
                host.role = role
                host.role_confidence = 0.9
                corr._refresh_topology_fields(host)
                self.assertEqual(expected_node_role, host.node_role)

    def test_automated_12_external_versus_internal_host_classification(self) -> None:
        store = InMemoryLibrarian()
        corr = correlator(store)

        private_host = host_entity(host_id="private_host")
        private_host.ips.add("192.168.1.10")
        private_host.role = "workstation"
        private_host.role_confidence = 0.7
        corr._refresh_topology_fields(private_host)

        public_host = host_entity(host_id="public_host")
        public_host.ips.add("8.8.8.8")
        public_host.role = "other"
        public_host.role_confidence = 0.3
        corr._refresh_topology_fields(public_host)

        self.assertFalse(private_host.is_external)
        self.assertTrue(public_host.is_external)

    def test_automated_13_parent_node_inference_for_internal_devices(self) -> None:
        store = InMemoryLibrarian()
        gateway = host_entity(host_id="gateway_host")
        gateway.ips.add("192.168.1.1")
        store.upsert_host(gateway)

        corr = correlator(store, gateway_ip="192.168.1.1")

        target = host_entity(host_id="internal_host")
        target.ips.add("192.168.1.120")
        target.role = "workstation"
        target.role_confidence = 0.8
        corr._refresh_topology_fields(target)

        self.assertEqual("gateway_host", target.parent_candidate)
        self.assertEqual(3, target.topology_layer)

    def test_automated_14_topology_layer_assignment_logic(self) -> None:
        store = InMemoryLibrarian()
        corr = correlator(store, local_ip="192.168.1.10", gateway_ip="192.168.1.1")

        gateway = host_entity(host_id="gateway")
        gateway.ips.add("192.168.1.1")
        gateway.role = "router"
        gateway.role_confidence = 0.95
        corr._refresh_topology_fields(gateway)
        store.upsert_host(gateway)

        local_host = host_entity(host_id="local")
        local_host.ips.add("192.168.1.10")
        local_host.role = "workstation"
        local_host.role_confidence = 0.7
        corr._refresh_topology_fields(local_host)

        external_host = host_entity(host_id="external")
        external_host.ips.add("1.1.1.1")
        external_host.role = "other"
        external_host.role_confidence = 0.2
        corr._refresh_topology_fields(external_host)

        self.assertEqual(1, gateway.topology_layer)
        self.assertEqual(3, local_host.topology_layer)
        self.assertEqual(0, external_host.topology_layer)

    def test_automated_15_same_segment_relationship_inference(self) -> None:
        store = InMemoryLibrarian()
        corr = correlator(store)

        src = host_entity(host_id="src")
        src.ips.add("192.168.1.20")
        src.role = "workstation"
        src.node_role = "workstation"

        dst = host_entity(host_id="dst")
        dst.ips.add("192.168.1.30")
        dst.role = "workstation"
        dst.node_role = "workstation"

        relation, confidence = corr._infer_observed_relationship(src, dst, "TCP")
        self.assertEqual("same-segment-peer", relation)
        self.assertGreater(confidence, 0.0)

    def test_automated_16_gateway_relationship_inference(self) -> None:
        store = InMemoryLibrarian()
        corr = correlator(store)

        src = host_entity(host_id="gateway_like")
        src.ips.add("192.168.1.1")
        src.role = "router"
        src.node_role = "router"

        dst = host_entity(host_id="internal_client")
        dst.ips.add("192.168.1.40")
        dst.role = "workstation"
        dst.node_role = "workstation"

        relation, confidence = corr._infer_observed_relationship(src, dst, "TCP")
        self.assertEqual("gateway-for", relation)
        self.assertGreater(confidence, 0.0)

    def test_automated_17_upstream_external_relationship_inference(self) -> None:
        store = InMemoryLibrarian()
        corr = correlator(store)

        src = host_entity(host_id="public_source")
        src.ips.add("8.8.8.8")
        src.role = "other"
        src.node_role = "unknown"

        dst = host_entity(host_id="private_router")
        dst.ips.add("192.168.1.1")
        dst.role = "router"
        dst.node_role = "router"

        relation, confidence = corr._infer_observed_relationship(src, dst, "TCP")
        self.assertEqual("upstream/external", relation)
        self.assertGreater(confidence, 0.0)

    def test_automated_18_relationship_strength_priority_handling(self) -> None:
        store = InMemoryLibrarian()
        corr = correlator(store)

        first_edge, first_is_new = corr._upsert_edge(
            a_host_id="a",
            b_host_id="b",
            proto="TCP",
            ts=None,
            src_port=1234,
            dst_port=443,
            relation="upstream/external",
            inferred=True,
            confidence=0.9,
            evidence={"initial"},
        )
        self.assertTrue(first_is_new)
        store.upsert_edge(first_edge)

        second_edge, second_is_new = corr._upsert_edge(
            a_host_id="a",
            b_host_id="b",
            proto="TCP",
            ts=None,
            src_port=5555,
            dst_port=80,
            relation="observed-traffic-peer",
            inferred=False,
            confidence=0.4,
            evidence={"weaker"},
        )
        self.assertFalse(second_is_new)
        self.assertEqual("upstream/external", second_edge.relationship_type)
        self.assertEqual("upstream/external", second_edge.relation)


if __name__ == "__main__":
    unittest.main()
