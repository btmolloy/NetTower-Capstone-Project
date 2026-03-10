from __future__ import annotations

import ipaddress
import platform
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


def list_interfaces() -> list[str]:
    """
    Best-effort interface listing.

    On Linux/macOS/Windows: socket.if_nameindex() often works.
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

    available = _all_interface_names()
    if not available:
        return True

    normalized_target = _normalize_interface_name(iface)
    return any(_normalize_interface_name(name) == normalized_target for name in available)


def detect_capture_interface() -> str:
    """
    Best-effort cross-platform interface detection.

    Preference order:
      1. interface with private RFC1918 IPv4
      2. interface with other non-loopback, non-APIPA IPv4
      3. preferred common names by platform
      4. first non-loopback interface

    On Windows, prefer psutil interface names because they match the names
    used when resolving addresses and are more human-meaningful (e.g. Ethernet).
    """
    candidates = _get_interface_candidates()

    if not candidates:
        raise ValueError("no usable network interfaces found")

    # Best case: private local LAN subnet
    private_candidates = [c for c in candidates if c["has_private_ipv4"]]
    if private_candidates:
        return private_candidates[0]["name"]

    # Next best: non-loopback IPv4 that is not APIPA
    normal_ipv4_candidates = [c for c in candidates if c["has_non_apipa_ipv4"]]
    if normal_ipv4_candidates:
        return normal_ipv4_candidates[0]["name"]

    system = platform.system().lower()
    preferred_names: list[str] = []

    if system == "darwin":
        preferred_names = ["en0", "en1"]
    elif system == "linux":
        preferred_names = [
            "eth0",
            "eth1",
            "ens33",
            "ens160",
            "ens192",
            "enp0s3",
            "enp3s0",
            "wlan0",
            "wlp2s0",
        ]
    elif system == "windows":
        preferred_names = [
            "ethernet",
            "wifi",
            "wi-fi",
        ]

    normalized_map = {_normalize_interface_name(c["name"]): c["name"] for c in candidates}
    for preferred in preferred_names:
        preferred_norm = _normalize_interface_name(preferred)
        if preferred_norm in normalized_map:
            return normalized_map[preferred_norm]

    return candidates[0]["name"]


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
        # Fall back to the best available interface candidate
        candidates = _get_interface_candidates()
        if not candidates:
            raise ValueError(f"interface not found: {iface}")
        matched_name = candidates[0]["name"]

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


def _all_interface_names() -> list[str]:
    names: list[str] = []

    for name in list_interfaces():
        if name not in names:
            names.append(name)

    if psutil is not None:
        try:
            for name in psutil.net_if_addrs().keys():
                if name not in names:
                    names.append(name)
        except Exception:
            pass

    return names


def _get_interface_candidates() -> list[dict[str, object]]:
    """
    Build ranked interface candidates using psutil when available.
    """
    candidates: list[dict[str, object]] = []

    if psutil is not None:
        try:
            iface_addrs_map = psutil.net_if_addrs()
        except Exception:
            iface_addrs_map = {}

        for iface_name, iface_addrs in iface_addrs_map.items():
            normalized_name = _normalize_interface_name(iface_name)
            if normalized_name in {"lo", "lo0", "loopback", "localhost"}:
                continue

            has_private_ipv4 = False
            has_non_apipa_ipv4 = False
            has_any_ipv4 = False

            for addr in iface_addrs:
                if addr.family != socket.AF_INET or not addr.address:
                    continue

                ip_str = addr.address
                if _is_loopback_ipv4(ip_str):
                    continue

                has_any_ipv4 = True

                if not _is_apipa_ipv4(ip_str):
                    has_non_apipa_ipv4 = True

                if _is_private_rfc1918_ipv4(ip_str):
                    has_private_ipv4 = True

            candidates.append(
                {
                    "name": iface_name,
                    "has_private_ipv4": has_private_ipv4,
                    "has_non_apipa_ipv4": has_non_apipa_ipv4,
                    "has_any_ipv4": has_any_ipv4,
                }
            )

        candidates.sort(
            key=lambda c: (
                not bool(c["has_private_ipv4"]),
                not bool(c["has_non_apipa_ipv4"]),
                not bool(c["has_any_ipv4"]),
                str(c["name"]).lower(),
            )
        )

        if candidates:
            return candidates

    # Fallback if psutil data is unavailable
    for iface_name in list_interfaces():
        normalized_name = _normalize_interface_name(iface_name)
        if normalized_name in {"lo", "lo0", "loopback", "localhost"}:
            continue

        candidates.append(
            {
                "name": iface_name,
                "has_private_ipv4": False,
                "has_non_apipa_ipv4": False,
                "has_any_ipv4": False,
            }
        )

    return candidates


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