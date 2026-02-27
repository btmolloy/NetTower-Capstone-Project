from __future__ import annotations

from typing import Any, List, Optional

from backEnd.models.events import base_event, host_seen, port_seen, traffic_seen
from backEnd.models.types import event_meta, sensor_source, protocol, confidence_level


class extractor:
    """
    Normalize raw sensor outputs into canonical Event objects.

    Usage pattern (in main):
      items = extractor.to_events(bus_item)
      for event in items:
          ...

    Current behavior:
      - If item is already a base_event -> returns [item]
      - If item is a dict with a recognized 'type' -> converts to event(s)
      - Else -> returns []
    """

    def to_events(self, item: Any) -> List[base_event]:
        if item is None:
            return []

        # Already canonical
        if isinstance(item, base_event):
            return [item]

        # Raw dict form
        if isinstance(item, dict):
            event = self._from_dict(item)
            return [event] if event else []

        # Unknown raw type (string, bytes, etc.) not handled yet
        return []

    def _from_dict(self, data: dict[str, Any]) -> Optional[base_event]:
        event_type = (data.get("type") or "").strip().lower()
        meta = self._parse_meta(data.get("meta"))

        if meta is None:
            # If meta is missing, we can default, but it’s safer to require it
            return None

        if event_type == "host_seen":
            return host_seen(
                meta=meta,
                ip=str(data.get("ip", "")).strip(),
                mac=(str(data["mac"]).strip() if "mac" in data and data["mac"] is not None else None),
                hostname=(str(data["hostname"]).strip() if "hostname" in data and data["hostname"] is not None else None),
            )

        if event_type == "port_seen":
            proto_val = str(data.get("proto", "TCP")).strip().upper()
            proto_enum = protocol.tcp if proto_val == "TCP" else protocol.udp

            return port_seen(
                meta=meta,
                ip=str(data.get("ip", "")).strip(),
                port=int(data.get("port", 0)),
                proto=proto_enum,
                state=str(data.get("state", "unknown")).strip().lower(),
            )

        if event_type == "traffic_seen":
            proto_val = str(data.get("proto", "TCP")).strip().upper()
            if proto_val == "UDP":
                proto_enum = protocol.udp
            elif proto_val == "ICMP":
                proto_enum = protocol.icmp
            elif proto_val == "ARP":
                proto_enum = protocol.arp
            else:
                proto_enum = protocol.tcp

            return traffic_seen(
                meta=meta,
                src_ip=str(data.get("src_ip", "")).strip(),
                dst_ip=str(data.get("dst_ip", "")).strip(),
                proto=proto_enum,
                src_port=(int(data["src_port"]) if data.get("src_port") is not None else None),
                dst_port=(int(data["dst_port"]) if data.get("dst_port") is not None else None),
                bytes=int(data.get("bytes", 0)),
            )

        return None

    def _parse_meta(self, meta_obj: Any) -> Optional[event_meta]:
        if isinstance(meta_obj, event_meta):
            return meta_obj

        if isinstance(meta_obj, dict):
            source_val = str(meta_obj.get("source", "TCPDUMP")).strip().upper()
            iface_val = str(meta_obj.get("iface", "")).strip()
            conf_val = str(meta_obj.get("confidence", "MEDIUM")).strip().upper()

            source_enum = self._parse_source(source_val)
            conf_enum = self._parse_confidence(conf_val)

            if not iface_val:
                return None

            return event_meta(source=source_enum, iface=iface_val, confidence=conf_enum)

        return None

    def _parse_source(self, val: str) -> sensor_source:
        for s in sensor_source:
            if s.value == val:
                return s
        return sensor_source.tcpdump

    def _parse_confidence(self, val: str) -> confidence_level:
        for c in confidence_level:
            if c.value == val:
                return c
        return confidence_level.medium