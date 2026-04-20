from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from backEnd.models.types import event_meta, protocol


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class base_event:
    """
    Base class for all in-memory events flowing through the pipeline.

    Events are NOT stored by default. They represent observations.
    """
    meta: event_meta
    ts: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class host_seen(base_event):
    """
    Observation that a host exists/was observed.
    """
    ip: str = ""
    mac: Optional[str] = None
    hostname: Optional[str] = None


@dataclass(frozen=True)
class port_seen(base_event):
    """
    Observation that a port exists in some state for a host.
    """
    ip: str = ""
    port: int = 0
    proto: protocol = protocol.tcp
    state: str = "unknown"  # expected values later: open/closed/filtered/unknown


@dataclass(frozen=True)
class traffic_seen(base_event):
    """
    Observation of traffic from src -> dst. Prefer flow aggregation in passive_listener later.
    """
    src_ip: str = ""
    dst_ip: str = ""
    proto: protocol = protocol.tcp
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    bytes: int = 0


@dataclass(frozen=True)
class service_seen(base_event):
    """
    Observation that a network service fingerprint was identified on a host.
    """
    ip: str = ""
    port: int = 0
    proto: protocol = protocol.tcp
    service: Optional[str] = None
    product: Optional[str] = None
    version: Optional[str] = None
    extrainfo: Optional[str] = None


@dataclass(frozen=True)
class os_hint_seen(base_event):
    """
    Observation that a host OS fingerprint hint was identified.
    """
    ip: str = ""
    os_name: str = ""
    accuracy: int = 0


@dataclass(frozen=True)
class route_hop_seen(base_event):
    """
    Observation of a hop seen in path from scanner -> target host.
    """
    target_ip: str = ""
    hop_ip: str = ""
    hop_index: int = 0
