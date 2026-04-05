from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import ipaddress
import os
import platform
import re
import shutil
import subprocess
from threading import Lock
from typing import Any, Iterable
import xml.etree.ElementTree as ET

from backEnd.models.events import (
    host_seen,
    os_hint_seen,
    port_seen,
    route_hop_seen,
    service_seen,
)
from backEnd.models.types import confidence_level, event_meta, protocol, sensor_source
from backEnd.utils.logging import get_logger
from backEnd.utils.net import (
    is_valid_cidr,
    is_valid_ip,
    normalize_cidr,
    normalize_ip,
    normalize_mac,
)


_mac_re = re.compile(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b")
_nmap_lookup_lock = Lock()
_nmap_path_cache: str | None = None
_nmap_lookup_complete = False
_nmap_missing_warned = False

_ROLE_PORTS: tuple[int, ...] = (
    22,   # SSH
    53,   # DNS
    67,   # DHCP server
    68,   # DHCP client
    80,   # HTTP
    123,  # NTP
    161,  # SNMP
    443,  # HTTPS
    445,  # SMB
    3389, # RDP
    1900, # UPnP
)
_LIFE_PORT_STATES = {"open", "closed", "unfiltered"}
_INTERESTING_SERVICE_KEYWORDS = (
    "dns",
    "dhcp",
    "upnp",
    "snmp",
    "ssh",
    "smb",
    "rdp",
    "http",
    "https",
)


@dataclass
class nmap_port_observation:
    port: int
    proto: protocol
    state: str
    service: str | None = None
    product: str | None = None
    version: str | None = None
    extrainfo: str | None = None


@dataclass
class nmap_host_observation:
    ip: str
    mac: str | None = None
    hostname: str | None = None
    status_up: bool = False
    status_reason: str | None = None
    ports: list[nmap_port_observation] = field(default_factory=list)
    os_name: str | None = None
    os_accuracy: int = 0
    trace_hops: list[tuple[int, str]] = field(default_factory=list)

    def open_ports(self) -> set[int]:
        return {p.port for p in self.ports if p.state == "open"}

    def has_strong_life_evidence(self) -> bool:
        if self.mac:
            return True

        reason = (self.status_reason or "").strip().lower()
        if self.status_up and reason and reason not in {"user-set", "unknown"}:
            return True

        for p in self.ports:
            if p.state in _LIFE_PORT_STATES:
                return True

        return False


def run_discovery(
    cfg: Any,
    bus: Any,
    target: str,
    enable_icmp_scan: bool | None = None,
    enable_nmap_scan: bool | None = None,
) -> None:
    """
    Run an active discovery job.

    target can be:
      - single IP (targeted)
      - CIDR (interval sweep)

    Active scanning is intentionally layered:
      1) low-noise host existence + role-port scan
      2) selective deep scan (service/os/traceroute) for interesting hosts
    """
    log = get_logger(
        "backEnd.sensors.active_discovery",
        getattr(cfg, "log_level", "INFO"),
        getattr(cfg, "log_file", None),
    )

    timeout_seconds = max(1, int(getattr(cfg, "active_ping_timeout_seconds", 1)))
    ping_workers = max(1, min(256, int(getattr(cfg, "active_ping_workers", 48))))
    nmap_workers = max(1, min(64, int(getattr(cfg, "active_nmap_workers", max(4, ping_workers // 2)))))
    max_hosts_per_sweep = max(1, int(getattr(cfg, "active_max_hosts_per_sweep", 1024)))
    max_deep_hosts_per_sweep = max(0, int(getattr(cfg, "active_nmap_max_deep_hosts", 8)))

    do_icmp_scan = (
        bool(getattr(cfg, "enable_icmp_scan", True))
        if enable_icmp_scan is None
        else bool(enable_icmp_scan)
    )
    do_nmap_scan = _resolve_nmap_toggle(cfg, enable_nmap_scan)

    if not do_icmp_scan and not do_nmap_scan:
        log.info("active discovery: both ICMP and NMAP scans are disabled; skipping run")
        return

    if is_valid_cidr(target):
        cidr = normalize_cidr(target)
        host_targets = list(_iter_cidr_hosts(cidr))
        if len(host_targets) > max_hosts_per_sweep:
            log.warning(
                "active discovery: host target count exceeds cap; "
                f"target={cidr} total={len(host_targets)} cap={max_hosts_per_sweep}"
            )
            host_targets = host_targets[:max_hosts_per_sweep]

        log.info(
            "active discovery: sweep "
            f"target={cidr} hosts={len(host_targets)} icmp={do_icmp_scan} "
            f"nmap={do_nmap_scan} ping_workers={ping_workers} nmap_workers={nmap_workers} "
            f"timeout={timeout_seconds}s"
        )
        _run_sweep(
            cfg=cfg,
            bus=bus,
            host_targets=host_targets,
            do_icmp_scan=do_icmp_scan,
            do_nmap_scan=do_nmap_scan,
            ping_workers=ping_workers,
            nmap_workers=nmap_workers,
            timeout_seconds=timeout_seconds,
            max_deep_hosts=max_deep_hosts_per_sweep,
        )
        return

    if is_valid_ip(target):
        ip = normalize_ip(target)
        _run_targeted(
            cfg=cfg,
            bus=bus,
            ip=ip,
            do_icmp_scan=do_icmp_scan,
            do_nmap_scan=do_nmap_scan,
            timeout_seconds=timeout_seconds,
        )
        return

    log.warning(f"active discovery: invalid target '{target}' (expected IP or CIDR)")


def _run_sweep(
    cfg: Any,
    bus: Any,
    host_targets: list[str],
    do_icmp_scan: bool,
    do_nmap_scan: bool,
    ping_workers: int,
    nmap_workers: int,
    timeout_seconds: int,
    max_deep_hosts: int,
) -> None:
    iface = getattr(cfg, "interface", None)
    alive_ips: set[str] = set()

    if do_icmp_scan:
        with ThreadPoolExecutor(max_workers=ping_workers, thread_name_prefix="active-ping") as pool:
            futures = {pool.submit(_ping, ip, timeout_seconds): ip for ip in host_targets}
            for future in as_completed(futures):
                ip = futures[future]
                try:
                    is_alive = bool(future.result())
                except Exception:
                    is_alive = False
                if not is_alive:
                    continue

                alive_ips.add(ip)
                mac = _resolve_mac_for_ip(ip)
                _publish_host_seen(cfg, bus, ip=ip, iface=iface, mac=mac)

    if not do_nmap_scan:
        return

    nmap_targets = sorted(alive_ips) if do_icmp_scan else host_targets
    if not nmap_targets:
        return

    discovery_observations: list[nmap_host_observation] = []
    with ThreadPoolExecutor(max_workers=nmap_workers, thread_name_prefix="active-nmap-discovery") as pool:
        futures = {pool.submit(_nmap_discovery_scan, cfg, ip): ip for ip in nmap_targets}
        for future in as_completed(futures):
            ip = futures[future]
            try:
                obs = future.result()
            except Exception:
                obs = None
            if obs is None:
                continue

            # If ICMP already confirmed the host, we can accept the record.
            # Otherwise require stronger nmap evidence to avoid dead-host noise.
            emitted = _publish_nmap_observation(
                cfg=cfg,
                bus=bus,
                obs=obs,
                iface=iface,
                require_life_evidence=not do_icmp_scan,
            )
            if emitted:
                discovery_observations.append(obs)

    if max_deep_hosts <= 0:
        return

    deep_candidates: list[nmap_host_observation] = [
        obs for obs in discovery_observations if _is_interesting_host(obs)
    ]
    deep_candidates.sort(
        key=lambda h: (
            len(h.open_ports()),
            1 if h.has_strong_life_evidence() else 0,
            h.ip,
        ),
        reverse=True,
    )
    deep_candidates = deep_candidates[:max_deep_hosts]

    for obs in deep_candidates:
        _run_deep_nmap_for_host(
            cfg=cfg,
            bus=bus,
            ip=obs.ip,
            iface=iface,
            known_open_ports=sorted(obs.open_ports()),
            include_traceroute=False,
        )


def _run_targeted(
    cfg: Any,
    bus: Any,
    ip: str,
    do_icmp_scan: bool,
    do_nmap_scan: bool,
    timeout_seconds: int,
) -> None:
    iface = getattr(cfg, "interface", None)

    ping_alive = False
    if do_icmp_scan:
        ping_alive = _ping(ip, timeout_seconds=timeout_seconds)
        if ping_alive:
            # For targeted scans, avoid ARP-based MAC enrichment by default to prevent
            # gateway MAC conflation on off-link destinations.
            _publish_host_seen(cfg, bus, ip=ip, iface=iface, mac=None)

    if not do_nmap_scan:
        return

    obs = _nmap_discovery_scan(cfg, ip)
    if obs is None:
        return

    emitted = _publish_nmap_observation(
        cfg=cfg,
        bus=bus,
        obs=obs,
        iface=iface,
        require_life_evidence=not ping_alive,
    )

    # For targeted hosts, run deeper profiling once we have evidence of life.
    if emitted and (ping_alive or obs.has_strong_life_evidence() or _is_interesting_host(obs)):
        _run_deep_nmap_for_host(
            cfg=cfg,
            bus=bus,
            ip=ip,
            iface=iface,
            known_open_ports=sorted(obs.open_ports()),
            include_traceroute=True,
        )


def _iter_cidr_hosts(cidr: str) -> Iterable[str]:
    net = ipaddress.ip_network(cidr, strict=False)
    for host in net.hosts():
        yield str(host)


def _publish_host_seen(
    cfg: Any,
    bus: Any,
    ip: str,
    iface: str | None = None,
    mac: str | None = None,
) -> None:
    if iface is None:
        iface = getattr(cfg, "interface", None)

    meta = event_meta(
        source=sensor_source.ping,
        iface=iface,
        confidence=confidence_level.high,
    )
    bus.publish(host_seen(meta=meta, ip=ip, mac=mac))


def _resolve_mac_for_ip(ip: str) -> str | None:
    """
    Best-effort ARP lookup for local-network targets.
    Returns normalized aa:bb:cc:dd:ee:ff or None.
    """
    arp_path = shutil.which("arp")
    if not arp_path:
        return None

    system = platform.system().lower()
    commands: list[list[str]]
    if "windows" in system:
        commands = [[arp_path, "-a", ip]]
    else:
        commands = [[arp_path, "-n", ip], [arp_path, ip]]

    for cmd in commands:
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                check=False,
            )
        except Exception:
            continue

        output = proc.stdout or ""
        if not output:
            continue

        for line in output.splitlines():
            if ip not in line:
                continue
            match = _mac_re.search(line)
            if not match:
                continue
            raw = match.group(0).replace("-", ":")
            try:
                return normalize_mac(raw)
            except Exception:
                continue

    return None


def _ping(ip: str, timeout_seconds: int = 1) -> bool:
    """
    Cross-platform ping. Best-effort.
    """
    system = platform.system().lower()
    ping_path = shutil.which("ping")
    if not ping_path:
        return False

    timeout_seconds = max(1, int(timeout_seconds))
    try:
        if "windows" in system:
            timeout_ms = timeout_seconds * 1000
            cmd = [ping_path, "-n", "1", "-w", str(timeout_ms), ip]
        elif "darwin" in system:
            timeout_ms = timeout_seconds * 1000
            cmd = [ping_path, "-c", "1", "-W", str(timeout_ms), ip]
        else:
            cmd = [ping_path, "-c", "1", "-W", str(timeout_seconds), ip]

        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def _nmap_discovery_scan(cfg: Any, ip: str) -> nmap_host_observation | None:
    ports = str(getattr(cfg, "nmap_discovery_ports", ",".join(str(p) for p in _ROLE_PORTS)))
    host_timeout = f"{max(10, int(getattr(cfg, 'nmap_discovery_host_timeout_seconds', 15)))}s"
    args = [
        "-n",
        "-Pn",
        _nmap_tcp_scan_flag(),
        "-T3",
        "--max-retries",
        "1",
        "--host-timeout",
        host_timeout,
        "-p",
        ports,
        "-oX",
        "-",
        ip,
    ]
    observations = _nmap_scan_and_parse(cfg, args)
    if not observations:
        return None

    for obs in observations:
        if obs.ip == ip:
            return obs
    return observations[0]


def _run_deep_nmap_for_host(
    cfg: Any,
    bus: Any,
    ip: str,
    iface: str | None,
    known_open_ports: list[int],
    include_traceroute: bool,
) -> None:
    # Service/version scan on known open ports when available, otherwise role ports.
    service_ports = known_open_ports or list(_ROLE_PORTS)
    service_ports_str = ",".join(str(p) for p in sorted(set(service_ports))[:64])
    service_timeout = f"{max(12, int(getattr(cfg, 'nmap_service_host_timeout_seconds', 20)))}s"
    service_args = [
        "-n",
        "-Pn",
        "-sV",
        "--version-light",
        "--max-retries",
        "1",
        "--host-timeout",
        service_timeout,
        "-p",
        service_ports_str,
        "-oX",
        "-",
        ip,
    ]
    for obs in _nmap_scan_and_parse(cfg, service_args):
        _publish_nmap_observation(cfg, bus, obs, iface, require_life_evidence=False)

    # OS detection is supporting evidence only.
    os_timeout = f"{max(12, int(getattr(cfg, 'nmap_os_host_timeout_seconds', 20)))}s"
    os_args = [
        "-n",
        "-Pn",
        "-O",
        "--osscan-limit",
        "--max-os-tries",
        "1",
        "--host-timeout",
        os_timeout,
        "-oX",
        "-",
        ip,
    ]
    for obs in _nmap_scan_and_parse(cfg, os_args):
        _publish_nmap_observation(cfg, bus, obs, iface, require_life_evidence=False)

    if include_traceroute:
        trace_timeout = f"{max(12, int(getattr(cfg, 'nmap_trace_host_timeout_seconds', 20)))}s"
        trace_args = [
            "-n",
            "-Pn",
            "--traceroute",
            "-sn",
            "--host-timeout",
            trace_timeout,
            "-oX",
            "-",
            ip,
        ]
        for obs in _nmap_scan_and_parse(cfg, trace_args):
            _publish_nmap_observation(cfg, bus, obs, iface, require_life_evidence=False)


def _nmap_scan_and_parse(cfg: Any, args: list[str]) -> list[nmap_host_observation]:
    log = get_logger(
        "backEnd.sensors.active_discovery",
        getattr(cfg, "log_level", "INFO"),
        getattr(cfg, "log_file", None),
    )

    nmap_path = _resolve_nmap_path()
    if not nmap_path:
        global _nmap_missing_warned
        if not _nmap_missing_warned:
            log.warning(
                "nmap executable not found in PATH/common install locations; "
                "NMAP scans are skipped until nmap is installed."
            )
            _nmap_missing_warned = True
        return []

    cmd = [nmap_path, *args]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except Exception as exc:
        log.warning(f"nmap scan failed: {exc}")
        return []

    if proc.returncode != 0 and not proc.stdout:
        stderr = (proc.stderr or "").strip()
        if stderr:
            log.warning(f"nmap scan failed: {stderr}")
        return []

    xml_text = (proc.stdout or "").strip()
    if not xml_text:
        return []

    try:
        return _parse_nmap_xml_hosts(xml_text)
    except Exception as exc:
        log.warning(f"failed to parse nmap XML output: {exc}")
        return []


def _parse_nmap_xml_hosts(xml_text: str) -> list[nmap_host_observation]:
    root = ET.fromstring(xml_text)
    hosts: list[nmap_host_observation] = []

    for host_node in root.findall("./host"):
        ip: str | None = None
        mac: str | None = None

        for addr_node in host_node.findall("./address"):
            addr = (addr_node.get("addr") or "").strip()
            addr_type = (addr_node.get("addrtype") or "").strip().lower()
            if not addr:
                continue
            if addr_type == "ipv4":
                try:
                    ip = normalize_ip(addr)
                except Exception:
                    ip = None
            elif addr_type == "mac":
                try:
                    mac = normalize_mac(addr)
                except Exception:
                    mac = None

        if not ip:
            continue

        status_node = host_node.find("./status")
        status_state = (status_node.get("state") if status_node is not None else "") or ""
        status_reason = (status_node.get("reason") if status_node is not None else "") or ""
        status_up = status_state.strip().lower() == "up"

        hostname: str | None = None
        hostname_node = host_node.find("./hostnames/hostname")
        if hostname_node is not None:
            candidate = (hostname_node.get("name") or "").strip()
            if candidate:
                hostname = candidate

        ports: list[nmap_port_observation] = []
        for port_node in host_node.findall("./ports/port"):
            portid = port_node.get("portid")
            proto_raw = (port_node.get("protocol") or "tcp").strip().lower()
            try:
                port_num = int(str(portid))
            except Exception:
                continue

            state_node = port_node.find("./state")
            state = "unknown"
            if state_node is not None:
                state = ((state_node.get("state") or "unknown").strip().lower() or "unknown")

            proto_enum = protocol.tcp if proto_raw == "tcp" else protocol.udp

            service_node = port_node.find("./service")
            service_name = None
            product = None
            version = None
            extra = None
            if service_node is not None:
                service_name = _clean_optional_text(service_node.get("name"))
                product = _clean_optional_text(service_node.get("product"))
                version = _clean_optional_text(service_node.get("version"))
                extra = _clean_optional_text(service_node.get("extrainfo"))

            ports.append(
                nmap_port_observation(
                    port=port_num,
                    proto=proto_enum,
                    state=state,
                    service=service_name,
                    product=product,
                    version=version,
                    extrainfo=extra,
                )
            )

        best_os_name = None
        best_os_accuracy = 0
        for osmatch in host_node.findall("./os/osmatch"):
            os_name = _clean_optional_text(osmatch.get("name"))
            accuracy_raw = osmatch.get("accuracy")
            try:
                accuracy = int(str(accuracy_raw)) if accuracy_raw is not None else 0
            except Exception:
                accuracy = 0
            if os_name and accuracy >= best_os_accuracy:
                best_os_name = os_name
                best_os_accuracy = accuracy

        trace_hops: list[tuple[int, str]] = []
        for hop_node in host_node.findall("./trace/hop"):
            hop_ip_raw = (hop_node.get("ipaddr") or "").strip()
            ttl_raw = hop_node.get("ttl")
            try:
                hop_ip = normalize_ip(hop_ip_raw)
            except Exception:
                continue
            try:
                hop_index = int(str(ttl_raw)) if ttl_raw is not None else 0
            except Exception:
                hop_index = 0
            if hop_index <= 0:
                hop_index = len(trace_hops) + 1
            trace_hops.append((hop_index, hop_ip))

        trace_hops.sort(key=lambda x: x[0])
        hosts.append(
            nmap_host_observation(
                ip=ip,
                mac=mac,
                hostname=hostname,
                status_up=status_up,
                status_reason=status_reason or None,
                ports=ports,
                os_name=best_os_name,
                os_accuracy=best_os_accuracy,
                trace_hops=trace_hops,
            )
        )

    return hosts


def _publish_nmap_observation(
    cfg: Any,
    bus: Any,
    obs: nmap_host_observation,
    iface: str | None,
    require_life_evidence: bool,
) -> bool:
    """
    Publish normalized events from one parsed nmap host record.

    Returns True if at least one event was emitted.
    """
    if require_life_evidence and not obs.has_strong_life_evidence():
        return False

    meta = event_meta(
        source=sensor_source.nmap,
        iface=iface or getattr(cfg, "interface", ""),
        confidence=confidence_level.high,
    )

    emitted = False
    if obs.status_up or obs.has_strong_life_evidence():
        bus.publish(
            host_seen(
                meta=meta,
                ip=obs.ip,
                mac=obs.mac,
                hostname=obs.hostname,
            )
        )
        emitted = True

    for p in obs.ports:
        bus.publish(
            port_seen(
                meta=meta,
                ip=obs.ip,
                port=p.port,
                proto=p.proto,
                state=p.state,
            )
        )
        emitted = True

        if p.service or p.product or p.version or p.extrainfo:
            bus.publish(
                service_seen(
                    meta=meta,
                    ip=obs.ip,
                    port=p.port,
                    proto=p.proto,
                    service=p.service,
                    product=p.product,
                    version=p.version,
                    extrainfo=p.extrainfo,
                )
            )
            emitted = True

    if obs.os_name:
        bus.publish(
            os_hint_seen(
                meta=meta,
                ip=obs.ip,
                os_name=obs.os_name,
                accuracy=int(obs.os_accuracy),
            )
        )
        emitted = True

    for hop_index, hop_ip in obs.trace_hops:
        if hop_ip == obs.ip:
            continue
        bus.publish(
            route_hop_seen(
                meta=meta,
                target_ip=obs.ip,
                hop_ip=hop_ip,
                hop_index=hop_index,
            )
        )
        emitted = True

    return emitted


def _is_interesting_host(obs: nmap_host_observation) -> bool:
    open_ports = obs.open_ports()
    if open_ports.intersection(_ROLE_PORTS):
        return True

    if len(open_ports) >= 2:
        return True

    for p in obs.ports:
        service_tokens = " ".join(
            x.lower()
            for x in [p.service or "", p.product or "", p.version or "", p.extrainfo or ""]
            if x
        )
        if any(k in service_tokens for k in _INTERESTING_SERVICE_KEYWORDS):
            return True

    os_name = (obs.os_name or "").lower()
    if any(k in os_name for k in ("router", "switch", "firewall", "network appliance")):
        return True

    return False


def _resolve_nmap_toggle(cfg: Any, explicit_value: bool | None) -> bool:
    if explicit_value is not None:
        return bool(explicit_value)
    if hasattr(cfg, "enable_nmap_scan"):
        return bool(getattr(cfg, "enable_nmap_scan"))
    return bool(getattr(cfg, "enable_nmap", False))


def _nmap_tcp_scan_flag() -> str:
    # SYN scan requires elevated privileges on many platforms.
    # Fall back to connect scan to keep defaults working.
    if hasattr(os, "geteuid"):
        try:
            if os.geteuid() == 0:
                return "-sS"
        except Exception:
            pass
    return "-sT"


def _resolve_nmap_path() -> str | None:
    global _nmap_lookup_complete, _nmap_path_cache
    if _nmap_lookup_complete:
        return _nmap_path_cache

    with _nmap_lookup_lock:
        if not _nmap_lookup_complete:
            _nmap_path_cache = shutil.which("nmap")
            if not _nmap_path_cache:
                fallback_paths = (
                    "/opt/homebrew/bin/nmap",
                    "/usr/local/bin/nmap",
                    "/usr/bin/nmap",
                    r"C:\Program Files\Nmap\nmap.exe",
                    r"C:\Program Files (x86)\Nmap\nmap.exe",
                )
                for candidate in fallback_paths:
                    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                        _nmap_path_cache = candidate
                        break
            _nmap_lookup_complete = True

    return _nmap_path_cache


def _clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text

