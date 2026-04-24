from __future__ import annotations

from dataclasses import dataclass

from backEnd.models.entities import edge_entity, host_entity
from backEnd.models.types import confidence_level, event_meta, sensor_source


class InMemoryLibrarian:
    """
    Lightweight in-memory test double for correlator/librarian behavior.
    """

    def __init__(self) -> None:
        self.hosts_by_id: dict[str, host_entity] = {}
        self.edges_by_key: dict[str, edge_entity] = {}

    def find_host_by_mac(self, mac: str) -> host_entity | None:
        for host in self.hosts_by_id.values():
            if mac in host.macs:
                return host
        return None

    def find_host_by_ip(self, ip: str) -> host_entity | None:
        for host in self.hosts_by_id.values():
            if ip in host.ips:
                return host
        return None

    def find_host_by_id(self, host_id: str) -> host_entity | None:
        return self.hosts_by_id.get(host_id)

    def find_edge_by_key(self, edge_key: str) -> edge_entity | None:
        return self.edges_by_key.get(edge_key)

    def find_edge(self, a_host_id: str, b_host_id: str, proto: str) -> edge_entity | None:
        key = edge_entity.make_edge_key(a_host_id, b_host_id, proto)
        return self.edges_by_key.get(key)

    def upsert_host(self, entity: host_entity) -> None:
        self.hosts_by_id[entity.host_id] = entity

    def upsert_edge(self, entity: edge_entity) -> None:
        key = edge_entity.make_edge_key(entity.a_host_id, entity.b_host_id, entity.proto)
        self.edges_by_key[key] = entity

    def host_count(self) -> int:
        return len(self.hosts_by_id)

    def edge_count(self) -> int:
        return len(self.edges_by_key)


def make_meta(
    source: sensor_source = sensor_source.tcpdump,
    iface: str = "en0",
    confidence: confidence_level = confidence_level.medium,
) -> event_meta:
    return event_meta(source=source, iface=iface, confidence=confidence)


def apply_updates(
    store: InMemoryLibrarian,
    host_updates: list[host_entity],
    edge_updates: list[edge_entity],
) -> None:
    for host in host_updates:
        store.upsert_host(host)
    for edge in edge_updates:
        store.upsert_edge(edge)
