from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class host_entity:
    """
    Canonical stored state for a host.
    Intended to be upserted into Mongo and served to the UI.
    """
    host_id: str

    ips: set[str] = field(default_factory=set)
    macs: set[str] = field(default_factory=set)

    vendor: Optional[str] = None
    os_guess: Optional[str] = None

    first_seen: datetime = field(default_factory=utc_now)
    last_seen: datetime = field(default_factory=utc_now)

    # Stored as tuples to avoid inconsistent schemas:
    # (proto, port, state) e.g. ("TCP", 22, "open")
    ports: set[tuple[str, int, str]] = field(default_factory=set)

    def touch(self, ts: Optional[datetime] = None) -> None:
        """
        Update last_seen, used when a new event for this host arrives.
        """
        self.last_seen = ts or utc_now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "host_id": self.host_id,
            "ips": sorted(self.ips),
            "macs": sorted(self.macs),
            "vendor": self.vendor,
            "os_guess": self.os_guess,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "ports": sorted([(p, int(port), s) for (p, port, s) in self.ports]),
        }

    @staticmethod
    def from_dict(doc: dict[str, Any]) -> "host_entity":
        h = host_entity(host_id=doc["host_id"])
        h.ips = set(doc.get("ips", []))
        h.macs = set(doc.get("macs", []))
        h.vendor = doc.get("vendor")
        h.os_guess = doc.get("os_guess")
        h.first_seen = doc.get("first_seen", utc_now())
        h.last_seen = doc.get("last_seen", utc_now())
        h.ports = set(tuple(x) for x in doc.get("ports", []))
        return h


@dataclass
class edge_entity:
    """
    Canonical stored state for a relationship/traffic edge between two hosts.
    Key design choice: stable directional ordering by host_id, so we store one doc per pair.
    """
    a_host_id: str
    b_host_id: str
    proto: str  # e.g. "TCP", "UDP", "ICMP", "ARP"

    first_seen: datetime = field(default_factory=utc_now)
    last_seen: datetime = field(default_factory=utc_now)

    count: int = 0  # number of observations/flows/etc.

    # Optional: record port pairs involved: (src_port, dst_port)
    ports: set[tuple[Optional[int], Optional[int]]] = field(default_factory=set)

    @staticmethod
    def make_edge_key(a_host_id: str, b_host_id: str, proto: str) -> str:
        """
        Stable key used for uniqueness/indexing in Mongo.
        Ensures host pair order is consistent.
        """
        left, right = sorted([a_host_id, b_host_id])
        return f"{left}__{right}__{proto.upper()}"

    def edge_key(self) -> str:
        return edge_entity.make_edge_key(self.a_host_id, self.b_host_id, self.proto)

    def touch(self, ts: Optional[datetime] = None) -> None:
        self.last_seen = ts or utc_now()

    def to_dict(self) -> dict[str, Any]:
        left, right = sorted([self.a_host_id, self.b_host_id])
        return {
            "edge_key": self.edge_key(),
            "a_host_id": left,
            "b_host_id": right,
            "proto": self.proto.upper(),
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "count": int(self.count),
            "ports": sorted([(sp, dp) for (sp, dp) in self.ports]),
        }

    @staticmethod
    def from_dict(doc: dict[str, Any]) -> "edge_entity":
        e = edge_entity(
            a_host_id=doc["a_host_id"],
            b_host_id=doc["b_host_id"],
            proto=doc.get("proto", "").upper(),
        )
        e.first_seen = doc.get("first_seen", utc_now())
        e.last_seen = doc.get("last_seen", utc_now())
        e.count = int(doc.get("count", 0))
        e.ports = set(tuple(x) for x in doc.get("ports", []))
        return e