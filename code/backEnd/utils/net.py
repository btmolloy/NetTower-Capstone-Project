from __future__ import annotations

import ipaddress
import platform
import re
import socket
import subprocess
import threading
from typing import Optional

try:
    import psutil
except ImportError:
    psutil = None


_mac_re = re.compile(r"^[0-9a-fA-F]{2}([:\-]?[0-9a-fA-F]{2}){5}$")
_hostname_ptr_re = re.compile(r"\bname\s*=\s*(?P<host>[^\s]+)\.?\s*$", re.IGNORECASE)
_hostname_host_re = re.compile(
    r"\b(?:domain name pointer|pointer)\s+(?P<host>[^\s]+)\.?\s*$",
    re.IGNORECASE,
)
_socket_timeout_lock = threading.Lock()


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


def is_private_rfc1918_ipv4(ip: str) -> bool:
    """
    Return True when ip is in RFC1918 private IPv4 space:
      - 10.0.0.0/8
      - 172.16.0.0/12
      - 192.168.0.0/16
    """
    return _is_private_rfc1918_ipv4(ip.strip())


def is_private_rfc1918_cidr(cidr: str) -> bool:
    """
    Return True when the entire CIDR is inside RFC1918 private IPv4 space.
    """
    try:
        network = ipaddress.ip_network(cidr.strip(), strict=False)
    except ValueError:
        return False

    if not isinstance(network, ipaddress.IPv4Network):
        return False

    private_networks = (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
    )
    return any(network.subnet_of(private_net) for private_net in private_networks)


def detect_default_gateway_ipv4(iface: str | None = None) -> str:
    """
    Best-effort default gateway detection for the current host.

    If iface is provided, prefer default route scoped to that interface when possible.
    """
    iface_value = iface.strip() if isinstance(iface, str) else None
    system = platform.system().lower()

    if "darwin" in system:
        cmd = ["route", "-n", "get", "default"]
        if iface_value:
            cmd.extend(["-ifscope", iface_value])
        lines = _run_cmd_lines(cmd)
        gateway = _extract_gateway_from_route_get(lines)
        if gateway:
            return gateway

    if "linux" in system:
        cmd = ["ip", "-4", "route", "show", "default"]
        if iface_value:
            cmd.extend(["dev", iface_value])
        lines = _run_cmd_lines(cmd)
        gateway = _extract_gateway_from_ip_route(lines)
        if gateway:
            return gateway

    if "windows" in system:
        lines = _run_cmd_lines(["route", "print", "-4"])
        gateway = _extract_gateway_from_windows_route_print(lines, iface_value)
        if gateway:
            return gateway

    # Generic fallbacks
    for cmd in (
        ["ip", "-4", "route", "show", "default"],
        ["route", "-n", "get", "default"],
        ["netstat", "-rn"],
    ):
        lines = _run_cmd_lines(cmd)
        gateway = (
            _extract_gateway_from_ip_route(lines)
            or _extract_gateway_from_route_get(lines)
            or _extract_gateway_from_netstat(lines, iface_value)
        )
        if gateway:
            return gateway

    raise ValueError("default gateway IPv4 not found")


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


def detect_interface_ipv4(iface: str) -> str:
    """
    Detect the best IPv4 address for a given interface.

    Preference order:
    1. RFC1918 private address
    2. Non-APIPA address
    3. Any non-loopback IPv4
    """
    if not iface or not iface.strip():
        raise ValueError("interface is required for IPv4 detection")

    if psutil is None:
        raise ValueError(
            "psutil is required for interface IPv4 detection but is not installed"
        )

    iface_addrs_map = psutil.net_if_addrs()
    matched_name = _match_interface_name(iface.strip(), list(iface_addrs_map.keys()))
    if matched_name is None:
        raise ValueError(f"interface not found: {iface}")

    iface_addrs = iface_addrs_map.get(matched_name)
    if not iface_addrs:
        raise ValueError(f"interface not found: {iface}")

    best_private: str | None = None
    best_non_apipa: str | None = None
    best_any: str | None = None

    for addr in iface_addrs:
        if addr.family != socket.AF_INET or not addr.address:
            continue

        ip_str = addr.address
        if _is_loopback_ipv4(ip_str):
            continue

        if best_any is None:
            best_any = ip_str

        if not _is_apipa_ipv4(ip_str) and best_non_apipa is None:
            best_non_apipa = ip_str

        if _is_private_rfc1918_ipv4(ip_str) and best_private is None:
            best_private = ip_str

    chosen = best_private or best_non_apipa or best_any
    if chosen is None:
        raise ValueError(f"no IPv4 address found for interface: {matched_name}")

    return chosen


def detect_interface_mac(iface: str) -> str:
    """
    Detect the primary MAC address for a given interface.
    """
    if not iface or not iface.strip():
        raise ValueError("interface is required for MAC detection")

    if psutil is None:
        raise ValueError(
            "psutil is required for interface MAC detection but is not installed"
        )

    iface_addrs_map = psutil.net_if_addrs()
    matched_name = _match_interface_name(iface.strip(), list(iface_addrs_map.keys()))
    if matched_name is None:
        raise ValueError(f"interface not found: {iface}")

    iface_addrs = iface_addrs_map.get(matched_name)
    if not iface_addrs:
        raise ValueError(f"interface not found: {iface}")

    for addr in iface_addrs:
        candidate = (getattr(addr, "address", None) or "").strip()
        if not candidate:
            continue
        try:
            normalized = normalize_mac(candidate)
        except Exception:
            continue

        if normalized != "00:00:00:00:00:00":
            return normalized

    raise ValueError(f"no MAC address found for interface: {matched_name}")


def extract_oui(mac: str) -> Optional[str]:
    """
    Return the OUI prefix (first 3 bytes) as 'aa:bb:cc' or None if invalid.
    """
    try:
        norm = normalize_mac(mac)
        return ":".join(norm.split(":")[0:3])
    except Exception:
        return None


def resolve_ip_hostname(ip: str, timeout_seconds: float = 1.5) -> Optional[str]:
    """
    Best-effort reverse hostname lookup for an IP.

    Strategy:
      1) system resolver commands with explicit timeout (nslookup/host/getent)
      2) socket.gethostbyaddr fallback
    """
    try:
        norm_ip = normalize_ip(ip)
        ip_obj = ipaddress.ip_address(norm_ip)
    except Exception:
        return None

    if ip_obj.is_multicast or ip_obj.is_unspecified:
        return None

    timeout = max(0.2, float(timeout_seconds))

    command_candidates: list[list[str]] = []
    if shutil_which("getent"):
        command_candidates.append(["getent", "hosts", norm_ip])
    if shutil_which("nslookup"):
        command_candidates.append(["nslookup", norm_ip])
    if shutil_which("host"):
        command_candidates.append(["host", norm_ip])

    for cmd in command_candidates:
        hostname = _resolve_hostname_with_command(cmd, norm_ip, timeout)
        if hostname:
            return hostname

    return _resolve_hostname_with_socket(norm_ip, timeout)


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


def _run_cmd_lines(cmd: list[str]) -> list[str]:
    executable = cmd[0] if cmd else ""
    if not executable:
        return []
    if not shutil_which(executable):
        return []

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except Exception:
        return []

    text = (proc.stdout or "").strip()
    if not text:
        return []
    return [line.rstrip() for line in text.splitlines() if line.strip()]


def _extract_gateway_from_route_get(lines: list[str]) -> Optional[str]:
    for line in lines:
        match = re.search(r"\bgateway:\s*(\d+\.\d+\.\d+\.\d+)\b", line)
        if not match:
            continue
        try:
            ip_obj = ipaddress.ip_address(match.group(1))
        except ValueError:
            continue
        if isinstance(ip_obj, ipaddress.IPv4Address):
            return str(ip_obj)
    return None


def _extract_gateway_from_ip_route(lines: list[str]) -> Optional[str]:
    for line in lines:
        # Example: default via 10.10.30.1 dev en0 proto dhcp src 10.10.30.40
        match = re.search(r"\bdefault\s+via\s+(\d+\.\d+\.\d+\.\d+)\b", line)
        if not match:
            continue
        try:
            ip_obj = ipaddress.ip_address(match.group(1))
        except ValueError:
            continue
        if isinstance(ip_obj, ipaddress.IPv4Address):
            return str(ip_obj)
    return None


def _extract_gateway_from_netstat(lines: list[str], iface: str | None) -> Optional[str]:
    iface_l = iface.lower() if isinstance(iface, str) else None
    candidates: list[str] = []

    for line in lines:
        compact = " ".join(line.split())
        lower = compact.lower()
        if not (lower.startswith("default ") or lower.startswith("0.0.0.0 ")):
            continue
        parts = compact.split(" ")
        if len(parts) < 2:
            continue

        if iface_l and len(parts) >= 1 and parts[-1].lower() != iface_l:
            continue

        gateway_raw = parts[1]
        try:
            ip_obj = ipaddress.ip_address(gateway_raw)
        except ValueError:
            continue
        if isinstance(ip_obj, ipaddress.IPv4Address):
            candidates.append(str(ip_obj))

    return candidates[0] if candidates else None


def _extract_gateway_from_windows_route_print(lines: list[str], iface: str | None) -> Optional[str]:
    iface_l = iface.lower() if isinstance(iface, str) else None

    for line in lines:
        compact = " ".join(line.split())
        # Route row format (IPv4):
        # 0.0.0.0 0.0.0.0 192.168.1.1 192.168.1.22 25
        parts = compact.split(" ")
        if len(parts) < 5:
            continue
        if parts[0] != "0.0.0.0" or parts[1] != "0.0.0.0":
            continue

        gateway_raw = parts[2]
        interface_raw = parts[3]

        if iface_l and iface_l not in compact.lower():
            # windows route print generally includes interface IP, not name;
            # do not hard-filter if interface name is unavailable in line.
            pass

        try:
            gateway_ip = ipaddress.ip_address(gateway_raw)
            _ = ipaddress.ip_address(interface_raw)
        except ValueError:
            continue
        if isinstance(gateway_ip, ipaddress.IPv4Address):
            return str(gateway_ip)

    return None


def shutil_which(executable: str) -> Optional[str]:
    # local helper to avoid importing shutil at module import time unless needed
    try:
        import shutil
    except Exception:
        return None
    return shutil.which(executable)


def _resolve_hostname_with_command(cmd: list[str], ip: str, timeout_seconds: float) -> Optional[str]:
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except Exception:
        return None

    output_lines = []
    for chunk in (proc.stdout or "", proc.stderr or ""):
        if chunk:
            output_lines.extend(chunk.splitlines())

    for raw_line in output_lines:
        line = raw_line.strip()
        if not line:
            continue

        lowered = line.lower()
        if "can't find" in lowered or "not found" in lowered:
            continue

        match = _hostname_ptr_re.search(line)
        if match:
            candidate = _clean_hostname_candidate(match.group("host"), ip)
            if candidate:
                return candidate

        match = _hostname_host_re.search(line)
        if match:
            candidate = _clean_hostname_candidate(match.group("host"), ip)
            if candidate:
                return candidate

        if cmd and cmd[0] == "getent":
            # getent hosts output: "<ip> <hostname> [aliases]"
            parts = line.split()
            if len(parts) >= 2 and parts[0] == ip:
                candidate = _clean_hostname_candidate(parts[1], ip)
                if candidate:
                    return candidate

    return None


def _resolve_hostname_with_socket(ip: str, timeout_seconds: float) -> Optional[str]:
    with _socket_timeout_lock:
        previous_timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(timeout_seconds)
            try:
                primary, aliases, _ = socket.gethostbyaddr(ip)
            except Exception:
                return None
        finally:
            socket.setdefaulttimeout(previous_timeout)

    for candidate in [primary, *aliases]:
        cleaned = _clean_hostname_candidate(candidate, ip)
        if cleaned:
            return cleaned
    return None


def _clean_hostname_candidate(hostname: str | None, ip: str) -> Optional[str]:
    if hostname is None:
        return None
    text = str(hostname).strip().strip(".")
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"?", "unknown", "localhost", "localhost.localdomain"}:
        return None
    if lowered == ip.lower():
        return None
    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", text):
        return None
    return text[:255]
