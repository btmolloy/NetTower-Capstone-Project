from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Tuple

from backEnd.models.entities import edge_entity, host_entity
from backEnd.models.events import (
    base_event,
    host_seen,
    os_hint_seen,
    port_seen,
    route_hop_seen,
    service_seen,
    traffic_seen,
)
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
            host, existed = self._get_or_create_host(
                ip=(event.ip.strip() if event.ip else ""),
                mac=(event.mac.strip() if event.mac else None),
                hostname=(event.hostname.strip() if event.hostname else None),
                vendor=self._as_str_or_none(enrichment_data.get("vendor")),
                os_guess=self._as_str_or_none(enrichment_data.get("os_guess")),
                role_hint=self._as_str_or_none(enrichment_data.get("role_hint")),
                ts=ts,
            )
            self._refresh_host_inference(host, enrichment_data)
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
            host, existed = self._get_or_create_host(
                ip=(event.ip.strip() if event.ip else ""),
                mac=None,
                hostname=None,
                vendor=None,
                os_guess=self._as_str_or_none(enrichment_data.get("os_guess")),
                role_hint=self._as_str_or_none(enrichment_data.get("role_hint")),
                ts=ts,
            )

            proto_str = event.proto.value if hasattr(event.proto, "value") else str(event.proto)
            state = (event.state or "unknown").strip().lower()
            host.ports.add((proto_str.upper(), int(event.port), state))
            host.touch(ts)

            if not host.os_guess:
                inferred_os = self._infer_os_guess_from_ports(host.ports)
                if inferred_os:
                    host.os_guess = inferred_os

            self._refresh_host_inference(host, enrichment_data)
            host_updates.append(host)

            if not existed:
                signals = correlation_signals(
                    new_host_detected=True,
                    targeted_scan_ip=next(iter(host.ips), None),
                    new_edge_detected=False,
                )
            return host_updates, edge_updates, signals

        # -------------------------
        # service_seen
        # -------------------------
        if isinstance(event, service_seen):
            host, existed = self._get_or_create_host(
                ip=(event.ip.strip() if event.ip else ""),
                mac=None,
                hostname=None,
                vendor=None,
                os_guess=self._as_str_or_none(enrichment_data.get("os_guess")),
                role_hint=self._as_str_or_none(enrichment_data.get("role_hint")),
                ts=ts,
            )
            proto_str = event.proto.value if hasattr(event.proto, "value") else str(event.proto)
            host.services.add(
                (
                    proto_str.upper(),
                    int(event.port),
                    self._safe_text(event.service),
                    self._safe_text(event.product),
                    self._safe_text(event.version),
                    self._safe_text(event.extrainfo),
                )
            )
            host.touch(ts)
            self._refresh_host_inference(host, enrichment_data)
            host_updates.append(host)

            if not existed:
                signals = correlation_signals(
                    new_host_detected=True,
                    targeted_scan_ip=next(iter(host.ips), None),
                    new_edge_detected=False,
                )
            return host_updates, edge_updates, signals

        # -------------------------
        # os_hint_seen
        # -------------------------
        if isinstance(event, os_hint_seen):
            host, existed = self._get_or_create_host(
                ip=(event.ip.strip() if event.ip else ""),
                mac=None,
                hostname=None,
                vendor=None,
                os_guess=(event.os_name.strip() if event.os_name else None),
                role_hint=self._as_str_or_none(enrichment_data.get("role_hint")),
                ts=ts,
            )
            if event.os_name:
                incoming_os = event.os_name.strip()
                # Prefer higher-confidence OS hints when present.
                if event.accuracy >= 60 or not host.os_guess:
                    host.os_guess = incoming_os
            host.touch(ts)
            self._refresh_host_inference(host, enrichment_data)
            host_updates.append(host)

            if not existed:
                signals = correlation_signals(
                    new_host_detected=True,
                    targeted_scan_ip=next(iter(host.ips), None),
                    new_edge_detected=False,
                )
            return host_updates, edge_updates, signals

        # -------------------------
        # route_hop_seen
        # -------------------------
        if isinstance(event, route_hop_seen):
            target_ip_raw = event.target_ip.strip() if event.target_ip else ""
            hop_ip_raw = event.hop_ip.strip() if event.hop_ip else ""

            try:
                target_ip = normalize_ip(target_ip_raw)
                hop_ip = normalize_ip(hop_ip_raw)
            except ValueError:
                return host_updates, edge_updates, signals

            target_host, target_existed = self._get_or_create_host(
                ip=target_ip,
                mac=None,
                hostname=None,
                vendor=None,
                os_guess=None,
                role_hint=None,
                ts=ts,
            )
            hop_host, hop_existed = self._get_or_create_host(
                ip=hop_ip,
                mac=None,
                hostname=None,
                vendor=None,
                os_guess="Network appliance" if int(event.hop_index) == 1 else None,
                role_hint="network",
                ts=ts,
            )

            target_host.touch(ts)
            hop_host.touch(ts)
            self._refresh_host_inference(target_host, enrichment_data)
            self._refresh_host_inference(hop_host, {"role_hint": "network"})
            host_updates.extend([target_host, hop_host])

            if hop_host.host_id != target_host.host_id:
                relation_confidence = max(0.5, min(0.95, 1.0 - (0.07 * max(0, int(event.hop_index) - 1))))
                edge, edge_new = self._upsert_edge(
                    a_host_id=hop_host.host_id,
                    b_host_id=target_host.host_id,
                    proto="ROUTE",
                    ts=ts,
                    src_port=None,
                    dst_port=None,
                    relation="route_hop",
                    inferred=True,
                    confidence=relation_confidence,
                    evidence={f"traceroute_hop_{int(event.hop_index)}"},
                )
                edge_updates.append(edge)
            else:
                edge_new = False

            targeted_ip = None
            new_host = False
            if not target_existed and target_host.ips:
                targeted_ip = next(iter(target_host.ips), None)
                new_host = True
            elif not hop_existed and hop_host.ips:
                targeted_ip = next(iter(hop_host.ips), None)
                new_host = True

            signals = correlation_signals(
                new_host_detected=new_host,
                targeted_scan_ip=targeted_ip,
                new_edge_detected=edge_new,
            )
            return host_updates, edge_updates, signals

        # -------------------------
        # traffic_seen
        # -------------------------
        if isinstance(event, traffic_seen):
            src_ip_raw = event.src_ip.strip() if event.src_ip else ""
            dst_ip_raw = event.dst_ip.strip() if event.dst_ip else ""

            try:
                src_ip = normalize_ip(src_ip_raw)
                dst_ip = normalize_ip(dst_ip_raw)
            except ValueError:
                return host_updates, edge_updates, signals

            src_host, src_existed = self._get_or_create_host(
                ip=src_ip,
                mac=None,
                hostname=None,
                vendor=None,
                os_guess=None,
                role_hint=None,
                ts=ts,
            )
            src_host.touch(ts)
            self._refresh_host_inference(src_host, enrichment_data)
            host_updates.append(src_host)

            # Destination host is only considered "alive" once we have observed it
            # directly (e.g., as packet source, host_seen, or port_seen). Avoid
            # creating dst entries for outbound scan attempts.
            dst_host = self._librarian.find_host_by_ip(dst_ip)
            if not dst_host:
                signals = correlation_signals(
                    new_host_detected=not src_existed,
                    targeted_scan_ip=next(iter(src_host.ips), None) if not src_existed else None,
                    new_edge_detected=False,
                )
                return host_updates, edge_updates, signals

            if dst_host.host_id != src_host.host_id:
                dst_host.touch(ts)
                self._refresh_host_inference(dst_host, enrichment_data)
                host_updates.append(dst_host)
            else:
                signals = correlation_signals(
                    new_host_detected=not src_existed,
                    targeted_scan_ip=next(iter(src_host.ips), None) if not src_existed else None,
                    new_edge_detected=False,
                )
                return host_updates, edge_updates, signals

            proto_str = event.proto.value if hasattr(event.proto, "value") else str(event.proto)
            proto_str = proto_str.upper()

            edge, edge_new = self._upsert_edge(
                a_host_id=src_host.host_id,
                b_host_id=dst_host.host_id,
                proto=proto_str,
                ts=ts,
                src_port=event.src_port,
                dst_port=event.dst_port,
                relation="traffic",
                inferred=False,
                confidence=1.0,
                evidence=None,
            )
            edge_updates.append(edge)

            targeted_ip: Optional[str] = None
            new_host = False
            if not src_existed and src_host.ips:
                targeted_ip = next(iter(src_host.ips), None)
                new_host = True

            signals = correlation_signals(
                new_host_detected=new_host,
                targeted_scan_ip=targeted_ip,
                new_edge_detected=edge_new,
            )
            return host_updates, edge_updates, signals

        # Unknown/unhandled event type => no updates
        return host_updates, edge_updates, signals

    def _upsert_edge(
        self,
        a_host_id: str,
        b_host_id: str,
        proto: str,
        ts: Optional[datetime],
        src_port: Optional[int],
        dst_port: Optional[int],
        relation: str,
        inferred: bool,
        confidence: float,
        evidence: Optional[set[str]],
    ) -> tuple[edge_entity, bool]:
        existing_edge = self._librarian.find_edge(a_host_id, b_host_id, proto)
        if existing_edge:
            existing_edge.count += 1
            existing_edge.touch(ts)
            if src_port is not None or dst_port is not None:
                existing_edge.ports.add((src_port, dst_port))
            existing_edge.relation = relation or existing_edge.relation or "traffic"
            existing_edge.inferred = bool(existing_edge.inferred or inferred)
            existing_edge.confidence = max(float(existing_edge.confidence), float(confidence))
            if evidence:
                existing_edge.evidence.update(str(x) for x in evidence)
            return existing_edge, False

        new_edge = edge_entity(
            a_host_id=a_host_id,
            b_host_id=b_host_id,
            proto=proto,
            relation=relation or "traffic",
            inferred=bool(inferred),
            confidence=float(confidence),
            evidence=set(str(x) for x in (evidence or set())),
        )
        new_edge.first_seen = ts or new_edge.first_seen
        new_edge.last_seen = ts or new_edge.last_seen
        new_edge.count = 1
        if src_port is not None or dst_port is not None:
            new_edge.ports.add((src_port, dst_port))
        return new_edge, True

    def _get_or_create_host(
        self,
        ip: str,
        mac: Optional[str],
        hostname: Optional[str],
        vendor: Optional[str],
        os_guess: Optional[str],
        role_hint: Optional[str],
        ts: Optional[datetime],
    ) -> Tuple[host_entity, bool]:
        """
        Returns: (host_entity, existed_in_db)
        """
        norm_ip: Optional[str] = None
        norm_mac: Optional[str] = None
        norm_hostname = self._clean_hostname(hostname)

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

        if found:
            if norm_ip:
                found.ips.add(norm_ip)
            if norm_mac:
                found.macs.add(norm_mac)
            if norm_hostname:
                found.hostnames.add(norm_hostname)
            if vendor and not found.vendor:
                found.vendor = vendor
            if os_guess and not found.os_guess:
                found.os_guess = os_guess
            if role_hint:
                self._apply_role_hint(found, role_hint)
            found.touch(ts)
            return found, True

        host_id = self._make_host_id(norm_mac, norm_ip)
        new_host = host_entity(host_id=host_id)
        if norm_ip:
            new_host.ips.add(norm_ip)
        if norm_mac:
            new_host.macs.add(norm_mac)
        if norm_hostname:
            new_host.hostnames.add(norm_hostname)
        if vendor:
            new_host.vendor = vendor
        if os_guess:
            new_host.os_guess = os_guess
        if role_hint:
            self._apply_role_hint(new_host, role_hint)

        if ts:
            new_host.first_seen = ts
            new_host.last_seen = ts
        return new_host, False

    def _refresh_host_inference(self, host: host_entity, enrichment_data: Optional[dict[str, Any]]) -> None:
        scores: dict[str, float] = {}

        def add(role: str, weight: float) -> None:
            key = str(role).strip().lower()
            if not key or weight <= 0:
                return
            scores[key] = scores.get(key, 0.0) + float(weight)

        role_hint = None
        if isinstance(enrichment_data, dict):
            role_hint = self._as_str_or_none(enrichment_data.get("role_hint"))
        if role_hint:
            add(role_hint, 2.5)

        vendor = (host.vendor or "").lower()
        if any(k in vendor for k in ("cisco", "ubiquiti", "juniper", "mikrotik", "netgear", "tp-link", "asus")):
            add("network", 3.5)
            add("router", 2.5)
        if any(k in vendor for k in ("synology", "qnap")):
            add("storage", 3.0)
            add("server", 1.0)
        if any(k in vendor for k in ("canon", "epson", "xerox", "brother", "lexmark")):
            add("printer", 3.5)
        if "raspberry" in vendor:
            add("iot", 2.5)
            add("server", 1.0)
        if any(k in vendor for k in ("apple", "samsung", "google")):
            add("client", 1.5)
        if any(k in vendor for k in ("dell", "lenovo", "hewlett", "hp", "microsoft")):
            add("workstation", 1.5)

        open_ports = {
            int(port)
            for (_proto, port, state) in host.ports
            if str(state).strip().lower() == "open"
        }
        if 53 in open_ports:
            add("dns", 4.0)
            add("network", 1.0)
        if 67 in open_ports or 68 in open_ports:
            add("dhcp", 4.0)
            add("network", 1.0)
        if 161 in open_ports:
            add("network", 2.0)
        if 1900 in open_ports:
            add("network", 2.0)
            add("iot", 1.0)
        if 445 in open_ports or 139 in open_ports:
            add("workstation", 2.0)
            add("server", 1.0)
        if 3389 in open_ports:
            add("workstation", 2.0)
            add("server", 1.0)
        if 22 in open_ports:
            add("server", 1.5)
            add("network", 0.5)
        if 80 in open_ports or 443 in open_ports:
            add("server", 1.0)
        if len(open_ports) >= 4:
            add("server", 1.0)

        for service_record in host.services:
            if not isinstance(service_record, tuple):
                continue
            parts = list(service_record) + ["", "", "", "", "", ""]
            service = self._safe_text(parts[2])
            product = self._safe_text(parts[3])
            version = self._safe_text(parts[4])
            extra = self._safe_text(parts[5])
            tokens = " ".join(
                [
                    service.lower(),
                    product.lower(),
                    version.lower(),
                    extra.lower(),
                ]
            )
            if any(k in tokens for k in ("dnsmasq", "bind", "unbound")):
                add("dns", 4.0)
                add("network", 2.0)
            if "dhcp" in tokens:
                add("dhcp", 4.0)
                add("network", 2.0)
            if any(k in tokens for k in ("upnp", "miniupnpd", "igd")):
                add("router", 2.0)
                add("network", 2.0)
            if "snmp" in tokens:
                add("network", 2.0)
            if any(k in tokens for k in ("dropbear", "busybox", "routeros", "openwrt")):
                add("router", 3.0)
                add("network", 2.0)
            if any(k in tokens for k in ("ipp", "printer", "cups")):
                add("printer", 3.0)
            if any(k in tokens for k in ("microsoft-ds", "netbios", "smb")):
                add("workstation", 1.0)
                add("server", 1.0)

        os_guess = (host.os_guess or "").lower()
        if "windows" in os_guess:
            add("workstation", 2.0)
        if "linux" in os_guess or "unix" in os_guess:
            add("server", 1.0)
        if any(k in os_guess for k in ("network appliance", "router", "switch", "firewall")):
            add("network", 3.0)
            add("router", 2.0)
        if "apple" in os_guess:
            add("client", 2.0)

        host.role_scores = {k: round(v, 3) for k, v in sorted(scores.items())}
        if not host.role_scores:
            host.role = None
            host.role_confidence = None
            return

        top_role, top_score = max(host.role_scores.items(), key=lambda x: (x[1], x[0]))
        if top_score < 2.0:
            host.role = None
            host.role_confidence = None
            return

        total = sum(host.role_scores.values())
        confidence = (top_score / total) if total > 0 else 0.0
        host.role = top_role
        host.role_confidence = round(max(0.05, min(0.99, confidence)), 3)

    def _apply_role_hint(self, host: host_entity, role_hint: str) -> None:
        role = str(role_hint).strip().lower()
        if not role:
            return
        host.role_scores[role] = max(float(host.role_scores.get(role, 0.0)), 2.0)

    def _make_host_id(self, norm_mac: Optional[str], norm_ip: Optional[str]) -> str:
        if norm_mac:
            compact = norm_mac.replace(":", "")
            return f"host_mac_{compact}"
        if norm_ip:
            safe = norm_ip.replace(":", "_").replace(".", "_")
            return f"host_ip_{safe}"
        return "host_unknown"

    def _infer_os_guess_from_ports(self, ports: set[tuple[str, int, str]]) -> Optional[str]:
        open_ports = {int(port) for (_proto, port, state) in ports if str(state).strip().lower() == "open"}
        if not open_ports:
            return None

        if open_ports.intersection({3389, 5985, 5986}):
            return "Windows"
        if open_ports.intersection({445, 139, 137, 135}):
            return "Windows or Samba host"
        if 22 in open_ports:
            return "Unix-like (SSH)"
        if open_ports.intersection({548, 62078}):
            return "Apple (macOS/iOS)"
        if open_ports.intersection({23, 161, 1900}):
            return "Network appliance"
        return None

    def _clean_hostname(self, hostname: Optional[str]) -> Optional[str]:
        if hostname is None:
            return None
        text = str(hostname).strip()
        if not text:
            return None
        return text[:255]

    def _as_str_or_none(self, value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return None
        text = value.strip()
        return text if text else None

    def _safe_text(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()
