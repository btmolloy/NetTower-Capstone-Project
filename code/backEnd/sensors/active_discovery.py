from __future__ import annotations

import ipaddress
import platform
import subprocess
from typing import Any, Iterable, Optional

from backEnd.models.events import host_seen, port_seen
from backEnd.models.types import event_meta, sensor_source, protocol, confidence_level
from backEnd.utils.logging import get_logger
from backEnd.utils.net import normalize_cidr, normalize_ip, is_valid_ip, is_valid_cidr


def run_discovery(cfg: Any, bus: Any, target: str) -> None:
    """
    Run an active discovery job.

    target can be:
      - single IP (targeted)
      - CIDR (interval sweep)
    """
    log = get_logger("backEnd.sensors.active_discovery", getattr(cfg, "log_level", "INFO"))

    if is_valid_cidr(target):
        cidr = normalize_cidr(target)
        log.info(f"active discovery: ping sweep target={cidr}")
        for ip in _iter_cidr_hosts(cidr):
            _ping_and_publish(cfg, bus, ip)
        return

    if is_valid_ip(target):
        ip = normalize_ip(target)
        log.info(f"active discovery: targeted ping target={ip}")
        _ping_and_publish(cfg, bus, ip)
        return

    log.warning(f"active discovery: invalid target '{target}' (expected IP or CIDR)")


def _iter_cidr_hosts(cidr: str) -> Iterable[str]:
    net = ipaddress.ip_network(cidr, strict=False)

    # IMPORTANT: for large networks this can be huge; later you can cap/slice or parallelize.
    for host in net.hosts():
        yield str(host)


def _ping_and_publish(cfg: Any, bus: Any, ip: str) -> None:
    iface = getattr(cfg, "interface", "eth0")
    timeout_seconds = int(getattr(cfg, "active_ping_timeout_seconds", 1))
    do_nmap = bool(getattr(cfg, "enable_nmap", False))

    meta = event_meta(
        source=sensor_source.ping,
        iface=iface,
        confidence=confidence_level.high,
    )

    if _ping(ip, timeout_seconds=timeout_seconds):
        bus.publish(host_seen(meta=meta, ip=ip))

        # Optional: nmap after we confirm host responds
        if do_nmap:
            _nmap_ports(cfg, bus, ip, iface=iface)


def _ping(ip: str, timeout_seconds: int = 1) -> bool:
    """
    Cross-platform ping. Best-effort.

    Linux/macOS: ping -c 1 -W <timeout>
    Windows: ping -n 1 -w <timeout_ms>
    """
    system = platform.system().lower()

    try:
        if "windows" in system:
            timeout_ms = max(1, int(timeout_seconds) * 1000)
            cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
        else:
            # macOS uses -W in ms in some versions; Linux uses seconds.
            # We'll prefer a conservative approach: use -W seconds if possible.
            cmd = ["ping", "-c", "1", "-W", str(max(1, int(timeout_seconds))), ip]

        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def _nmap_ports(cfg: Any, bus: Any, ip: str, iface: str) -> None:
    """
    Optional nmap scan. Emits port_seen events.
    If nmap isn't installed, silently skips.
    """
    log = get_logger("backEnd.sensors.active_discovery", getattr(cfg, "log_level", "INFO"))

    ports = getattr(cfg, "nmap_ports", "22,80,443,445,3389")
    args = ["nmap", "-n", "-Pn", "-p", str(ports), ip]

    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        log.warning("nmap not found; skipping port scan")
        return
    except Exception as exc:
        log.warning(f"nmap scan failed: {exc}")
        return

    if proc.returncode != 0:
        # nmap uses non-zero sometimes for partial failures; still parse stdout if present
        if not proc.stdout:
            return

    meta = event_meta(
        source=sensor_source.nmap,
        iface=iface,
        confidence=confidence_level.high,
    )

    for port, proto, state in _parse_nmap_ports(proc.stdout):
        bus.publish(
            port_seen(
                meta=meta,
                ip=ip,
                port=port,
                proto=proto,
                state=state,
            )
        )


def _parse_nmap_ports(output: str) -> list[tuple[int, protocol, str]]:
    """
    Very small parser for common nmap output lines like:
      22/tcp open  ssh
      80/tcp closed http

    Returns: (port, protocol_enum, state)
    """
    results: list[tuple[int, protocol, str]] = []

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if "/" not in line:
            continue

        # naive split; good enough for baseline
        parts = line.split()
        if len(parts) < 2:
            continue

        port_proto = parts[0]  # e.g. "22/tcp"
        state = parts[1].strip().lower()

        try:
            port_str, proto_str = port_proto.split("/", 1)
            port_val = int(port_str)
        except Exception:
            continue

        proto_enum = protocol.tcp if proto_str.lower() == "tcp" else protocol.udp
        results.append((port_val, proto_enum, state))

    return results