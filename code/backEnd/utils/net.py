from __future__ import annotations

import ipaddress
import re
import socket
from typing import Optional


_mac_re = re.compile(r"^[0-9a-fA-F]{2}([:\-]?[0-9a-fA-F]{2}){5}$")


def normalize_mac(mac: str) -> str:
    """
    Normalize MAC to lower-case colon-separated form: aa:bb:cc:dd:ee:ff

    Accepts:
      - aa:bb:cc:dd:ee:ff
      - aa-bb-cc-dd-ee-ff
      - aabbccddeeff
    """
    mac = mac.strip().lower().replace("-", ":")
    parts = mac.split(":")

    if len(parts) == 1:
        raw = parts[0]
        if len(raw) != 12:
            raise ValueError(f"invalid mac: {mac}")
        parts = [raw[i : i + 2] for i in range(0, 12, 2)]

    if len(parts) != 6 or any(len(p) != 2 for p in parts):
        raise ValueError(f"invalid mac: {mac}")

    normalized = ":".join(parts)

    # Final validation
    if not is_valid_mac(normalized):
        raise ValueError(f"invalid mac: {mac}")

    return normalized


def is_valid_mac(mac: str) -> bool:
    return _mac_re.match(mac.strip()) is not None


def normalize_ip(ip: str) -> str:
    """
    Normalize an IPv4/IPv6 address to its canonical string form.
    """
    try:
        return str(ipaddress.ip_address(ip.strip()))
    except ValueError as exc:
        raise ValueError(f"invalid ip: {ip}") from exc


def is_valid_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip.strip())
        return True
    except ValueError:
        return False


def normalize_cidr(cidr: str) -> str:
    """
    Normalize CIDR to canonical form. strict=False allows host bits set.
    Example: '192.168.1.10/24' -> '192.168.1.0/24'
    """
    try:
        return str(ipaddress.ip_network(cidr.strip(), strict=False))
    except ValueError as exc:
        raise ValueError(f"invalid cidr: {cidr}") from exc


def is_valid_cidr(cidr: str) -> bool:
    try:
        ipaddress.ip_network(cidr.strip(), strict=False)
        return True
    except ValueError:
        return False


def ip_in_cidr(ip: str, cidr: str) -> bool:
    net = ipaddress.ip_network(cidr.strip(), strict=False)
    addr = ipaddress.ip_address(ip.strip())
    return addr in net


def list_interfaces() -> list[str]:
    """
    Best-effort interface listing.

    On Linux/macOS: socket.if_nameindex() usually works.
    On some platforms/environments, it may not be available; returns [] then.
    """
    try:
        return [name for _, name in socket.if_nameindex()]
    except Exception:
        return []


def is_valid_interface(iface: str) -> bool:
    """
    Best-effort interface validation.
    If the platform can't list interfaces, returns True (non-blocking).
    """
    iface = iface.strip()
    if not iface:
        return False

    interfaces = list_interfaces()
    if not interfaces:
        return True  # do not hard-fail in limited environments

    return iface in interfaces


def safe_int(value: str, default: int) -> int:
    """
    Small helper for parsing ints in settings/env overrides.
    """
    try:
        return int(value)
    except Exception:
        return default


def extract_oui(mac: str) -> Optional[str]:
    """
    Return the OUI prefix (first 3 bytes) as 'aa:bb:cc' or None if invalid.
    """
    try:
        norm = normalize_mac(mac)
        return ":".join(norm.split(":")[0:3])
    except Exception:
        return None