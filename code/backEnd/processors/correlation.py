from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Tuple

from backEnd.models.entities import host_entity, edge_entity
from backEnd.models.events import base_event, host_seen, port_seen, traffic_seen
from backEnd.utils.net import normalize_ip, normalize_mac


@dataclass(frozen=True)
class correlation_signals:
    new_host_detected: bool = False
    targeted_scan_ip: Optional[str] = None
    new_edge_detected: bool = False


class correlator:
    """
    Correlate events into DB-backed entity updates.

    Inputs:
      - event (base_event subclass)
      - enrichment_data (dict)

    Outputs:
      - host_updates: list[host_entity]
      - edge_updates: list[edge_entity]
      - signals: correlation_signals
    """

    def __init__(self, librarian: Any) -> None:
        self._librarian = librarian

    def process(
        self,
        event: base_event,
        enrichment_data: Optional[dict[str, Any]] = None,
    ) -> Tuple[list[host_entity], list[edge_entity], correlation_signals]:
        enrichment_data = enrichment_data or {}

        host_updates: list[host_entity] = []
        edge_updates: list[edge_entity] = []

        signals = correlation_signals()

        ts = getattr(event, "ts", None)
        if not isinstance(ts, datetime):
            ts = None

        # -------------------------
        # host_seen
        # -------------------------
        if isinstance(event, host_seen):
            ip = event.ip.strip() if event.ip else ""
            mac = event.mac.strip() if event.mac else None

            vendor = enrichment_data.get("vendor")
            if not isinstance(vendor, str):
                vendor = None

            host, existed = self._get_or_create_host(ip=ip, mac=mac, vendor=vendor, ts=ts)

            # hostname isn't stored on host_entity right now; you can add later if desired.

            host_updates.append(host)

            if not existed:
                signals = correlation_signals(
                    new_host_detected=True,
                    targeted_scan_ip=next(iter(host.ips), None),
                    new_edge_detected=False,
                )

            return host_updates, edge_updates, signals

        # -------------------------
        # port_seen
        # -------------------------
        if isinstance(event, port_seen):
            ip = event.ip.strip() if event.ip else ""
            host, existed = self._get_or_create_host(ip=ip, mac=None, vendor=None, ts=ts)

            proto_str = event.proto.value if hasattr(event.proto, "value") else str(event.proto)
            state = (event.state or "unknown").strip().lower()

            # store proto as upper-case strings in entities for consistency
            host.ports.add((proto_str.upper(), int(event.port), state))
            host.touch(ts)

            host_updates.append(host)

            if not existed:
                signals = correlation_signals(
                    new_host_detected=True,
                    targeted_scan_ip=next(iter(host.ips), None),
                    new_edge_detected=False,
                )

            return host_updates, edge_updates, signals

        # -------------------------
        # traffic_seen
        # -------------------------
        if isinstance(event, traffic_seen):
            src_ip = event.src_ip.strip() if event.src_ip else ""
            dst_ip = event.dst_ip.strip() if event.dst_ip else ""

            src_host, src_existed = self._get_or_create_host(ip=src_ip, mac=None, vendor=None, ts=ts)
            dst_host, dst_existed = self._get_or_create_host(ip=dst_ip, mac=None, vendor=None, ts=ts)

            src_host.touch(ts)
            dst_host.touch(ts)

            host_updates.extend([src_host, dst_host])

            proto_str = event.proto.value if hasattr(event.proto, "value") else str(event.proto)
            proto_str = proto_str.upper()

            existing_edge = self._librarian.find_edge(src_host.host_id, dst_host.host_id, proto_str)

            if existing_edge:
                existing_edge.count += 1
                existing_edge.touch(ts)
                existing_edge.ports.add((event.src_port, event.dst_port))
                edge_updates.append(existing_edge)
                edge_new = False
            else:
                new_edge = edge_entity(
                    a_host_id=src_host.host_id,
                    b_host_id=dst_host.host_id,
                    proto=proto_str,
                )
                new_edge.first_seen = ts or new_edge.first_seen
                new_edge.last_seen = ts or new_edge.last_seen
                new_edge.count = 1
                new_edge.ports.add((event.src_port, event.dst_port))
                edge_updates.append(new_edge)
                edge_new = True

            # signals: if either host is new, prioritize one targeted scan ip
            targeted_ip: Optional[str] = None
            new_host = False

            if not src_existed and src_host.ips:
                targeted_ip = next(iter(src_host.ips), None)
                new_host = True
            elif not dst_existed and dst_host.ips:
                targeted_ip = next(iter(dst_host.ips), None)
                new_host = True

            signals = correlation_signals(
                new_host_detected=new_host,
                targeted_scan_ip=targeted_ip,
                new_edge_detected=edge_new,
            )

            return host_updates, edge_updates, signals

        # Unknown/unhandled event type => no updates
        return host_updates, edge_updates, signals

    # -------------------------
    # Internals
    # -------------------------

    def _get_or_create_host(
        self,
        ip: str,
        mac: Optional[str],
        vendor: Optional[str],
        ts: Optional[datetime],
    ) -> Tuple[host_entity, bool]:
        """
        Returns: (host_entity, existed_in_db)
        """
        norm_ip: Optional[str] = None
        norm_mac: Optional[str] = None

        if ip:
            try:
                norm_ip = normalize_ip(ip)
            except ValueError:
                norm_ip = None

        if mac:
            try:
                norm_mac = normalize_mac(mac)
            except ValueError:
                norm_mac = None

        found: Optional[host_entity] = None

        # Prefer MAC lookup when possible (more stable than IP)
        if norm_mac:
            found = self._librarian.find_host_by_mac(norm_mac)

        if not found and norm_ip:
            found = self._librarian.find_host_by_ip(norm_ip)

        existed = found is not None

        if found:
            if norm_ip:
                found.ips.add(norm_ip)
            if norm_mac:
                found.macs.add(norm_mac)

            if vendor and not found.vendor:
                found.vendor = vendor

            found.touch(ts)
            return found, True

        # create new
        host_id = self._make_host_id(norm_mac, norm_ip)

        new_host = host_entity(host_id=host_id)
        if norm_ip:
            new_host.ips.add(norm_ip)
        if norm_mac:
            new_host.macs.add(norm_mac)
        if vendor:
            new_host.vendor = vendor

        # Use event timestamp if provided
        if ts:
            new_host.first_seen = ts
            new_host.last_seen = ts

        return new_host, False

    def _make_host_id(self, norm_mac: Optional[str], norm_ip: Optional[str]) -> str:
        """
        Deterministic host_id:
          - Prefer MAC-based id when present
          - Else IP-based id
          - Else fallback unique-ish placeholder
        """
        if norm_mac:
            # host_mac_aabbccddeeff
            compact = norm_mac.replace(":", "")
            return f"host_mac_{compact}"

        if norm_ip:
            safe = norm_ip.replace(":", "_").replace(".", "_")
            return f"host_ip_{safe}"

        return "host_unknown"