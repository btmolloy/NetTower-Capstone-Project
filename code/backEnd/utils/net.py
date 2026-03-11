from __future__ import annotations

import ipaddress
import re
import socket
from typing import Optional

try:
    import psutil
except ImportError:
    psutil = None


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


def detect_interface_network_cidr(iface: str) -> str:
    """
    Detect the IPv4 network CIDR for a given interface.

    Example:
        address 10.10.30.234
        netmask 255.255.255.0
        returns 10.10.30.0/24
    """
    if not iface or not iface.strip():
        raise ValueError("interface is required for subnet detection")

    if psutil is None:
        raise ValueError(
            "psutil is required for automatic subnet detection but is not installed"
        )

    iface_addrs_map = psutil.net_if_addrs()
    matched_name = _match_interface_name(iface.strip(), list(iface_addrs_map.keys()))

    if matched_name is None:
        raise ValueError(f"interface not found: {iface}")

    iface_addrs = iface_addrs_map.get(matched_name)
    if not iface_addrs:
        raise ValueError(f"interface not found: {iface}")

    best_private: tuple[str, str] | None = None
    best_non_apipa: tuple[str, str] | None = None
    best_any: tuple[str, str] | None = None

    for addr in iface_addrs:
        if addr.family != socket.AF_INET or not addr.address or not addr.netmask:
            continue

        ip_str = addr.address
        netmask_str = addr.netmask

        if _is_loopback_ipv4(ip_str):
            continue

        if best_any is None:
            best_any = (ip_str, netmask_str)

        if not _is_apipa_ipv4(ip_str) and best_non_apipa is None:
            best_non_apipa = (ip_str, netmask_str)

        if _is_private_rfc1918_ipv4(ip_str) and best_private is None:
            best_private = (ip_str, netmask_str)

    chosen = best_private or best_non_apipa or best_any
    if chosen is None:
        raise ValueError(f"no IPv4 address/netmask found for interface: {matched_name}")

    network = ipaddress.ip_interface(f"{chosen[0]}/{chosen[1]}").network
    return str(network)


def extract_oui(mac: str) -> Optional[str]:
    """
    Return the OUI prefix (first 3 bytes) as 'aa:bb:cc' or None if invalid.
    """
    try:
        norm = normalize_mac(mac)
        return ":".join(norm.split(":")[0:3])
    except Exception:
        return None


def _normalize_interface_name(name: str) -> str:
    """
    Normalize interface names for loose matching across platforms.
    Example:
      'Ethernet 0' -> 'ethernet0'
      'ethernet_0' -> 'ethernet0'
      'Wi-Fi' -> 'wifi'
    """
    return re.sub(r"[\s_\-]+", "", name.strip().lower())


def _match_interface_name(requested_name: str, available_names: list[str]) -> str | None:
    """
    Try to match an interface name exactly, case-insensitively, or by normalized form.
    """
    if requested_name in available_names:
        return requested_name

    requested_lower = requested_name.lower()
    for name in available_names:
        if name.lower() == requested_lower:
            return name

    requested_norm = _normalize_interface_name(requested_name)
    for name in available_names:
        if _normalize_interface_name(name) == requested_norm:
            return name

    return None


def _is_loopback_ipv4(ip_str: str) -> bool:
    return ip_str.startswith("127.")


def _is_apipa_ipv4(ip_str: str) -> bool:
    return ip_str.startswith("169.254.")


def _is_private_rfc1918_ipv4(ip_str: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    if not isinstance(ip_obj, ipaddress.IPv4Address):
        return False

    return (
        ip_obj in ipaddress.ip_network("10.0.0.0/8")
        or ip_obj in ipaddress.ip_network("172.16.0.0/12")
        or ip_obj in ipaddress.ip_network("192.168.0.0/16")
    )