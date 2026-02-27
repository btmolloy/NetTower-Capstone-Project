from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class sensor_source(str, Enum):
    tcpdump = "TCPDUMP"
    nmap = "NMAP"
    ping = "PING"
    arp = "ARP"


class protocol(str, Enum):
    tcp = "TCP"
    udp = "UDP"
    icmp = "ICMP"
    arp = "ARP"


class confidence_level(str, Enum):
    low = "LOW"
    medium = "MEDIUM"
    high = "HIGH"


@dataclass(frozen=True)
class event_meta:
    """
    Metadata attached to every event so downstream processors can make consistent decisions.
    """
    source: sensor_source
    iface: str
    confidence: confidence_level = confidence_level.medium