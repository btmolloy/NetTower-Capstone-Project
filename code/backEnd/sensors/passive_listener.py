from __future__ import annotations

import re
import subprocess
import threading
from typing import Any, Optional

from backEnd.models.events import host_seen, traffic_seen
from backEnd.models.types import event_meta, sensor_source, protocol, confidence_level
from backEnd.utils.logging import get_logger
from backEnd.utils.net import normalize_ip


class passive_listener(threading.Thread):
    """
    Passive packet metadata listener.

    Starts tcpdump and publishes packet-derived events to the event_bus.
    Focus is topology/activity, NOT payload reconstruction.
    """

    # Example tcpdump IPv4 line (varies by platform/options):
    # IP 192.168.1.10.5353 > 224.0.0.251.5353: UDP, length 123
    _ip_line_re = re.compile(
        r"\bIP\s+(?P<src_ip>\d+\.\d+\.\d+\.\d+)(?:\.(?P<src_port>\d+))?\s+>\s+"
        r"(?P<dst_ip>\d+\.\d+\.\d+\.\d+)(?:\.(?P<dst_port>\d+))?\b"
    )

    # Example ARP line:
    # ARP, Request who-has 192.168.1.1 tell 192.168.1.10, length 28
    _arp_who_has_re = re.compile(
        r"\bARP.*who-has\s+(?P<target_ip>\d+\.\d+\.\d+\.\d+)\s+tell\s+(?P<src_ip>\d+\.\d+\.\d+\.\d+)\b",
        re.IGNORECASE,
    )

    def __init__(self, cfg: Any, bus: Any, stop_event: threading.Event) -> None:
        super().__init__(daemon=True)
        self._cfg = cfg
        self._bus = bus
        self._stop_event = stop_event
        self._log = get_logger("backEnd.sensors.passive_listener", getattr(cfg, "log_level", "INFO"))

        self._proc: Optional[subprocess.Popen[str]] = None

    def run(self) -> None:
        iface = getattr(self._cfg, "interface", "eth0")
        bpf_filter = getattr(self._cfg, "passive_bpf_filter", "arp or ip")

        cmd = [
            "tcpdump",
            "-l",          # line-buffered output
            "-n",          # don't resolve names
            "-i", iface,
            bpf_filter,
        ]

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            self._log.error("tcpdump not found. passive listener disabled.")
            return
        except Exception as exc:
            self._log.error(f"failed to start tcpdump: {exc}")
            return

        self._log.info(f"passive listener started on iface={iface} filter='{bpf_filter}'")

        try:
            assert self._proc.stdout is not None
            while not self._stop_event.is_set():
                line = self._proc.stdout.readline()
                if not line:
                    # process ended or no output; check stop, then continue
                    if self._proc.poll() is not None:
                        break
                    continue

                line = line.strip()
                if not line:
                    continue

                self._handle_line(line, iface)

        finally:
            self._shutdown_proc()
            self._log.info("passive listener stopped")

    def _handle_line(self, line: str, iface: str) -> None:
        # ARP -> host_seen (both src and target become interesting)
        arp_match = self._arp_who_has_re.search(line)
        if arp_match:
            try:
                src_ip = normalize_ip(arp_match.group("src_ip"))
                target_ip = normalize_ip(arp_match.group("target_ip"))
            except ValueError:
                return

            meta = event_meta(
                source=sensor_source.tcpdump,
                iface=iface,
                confidence=confidence_level.medium,
            )

            # We don't have MACs from this simple parse, so emit IP-only host sightings
            self._bus.publish(host_seen(meta=meta, ip=src_ip))
            self._bus.publish(host_seen(meta=meta, ip=target_ip))
            return

        # IPv4 traffic -> traffic_seen
        ip_match = self._ip_line_re.search(line)
        if ip_match:
            try:
                src_ip = normalize_ip(ip_match.group("src_ip"))
                dst_ip = normalize_ip(ip_match.group("dst_ip"))
            except ValueError:
                return

            src_port = ip_match.group("src_port")
            dst_port = ip_match.group("dst_port")

            meta = event_meta(
                source=sensor_source.tcpdump,
                iface=iface,
                confidence=confidence_level.low,  # passive parsing is best-effort
            )

            event = traffic_seen(
                meta=meta,
                src_ip=src_ip,
                dst_ip=dst_ip,
                proto=protocol.tcp,  # default; we aren’t parsing UDP/ICMP yet
                src_port=int(src_port) if src_port else None,
                dst_port=int(dst_port) if dst_port else None,
                bytes=0,
            )
            self._bus.publish(event)
            return

        # otherwise ignore (for now)

    def _shutdown_proc(self) -> None:
        if not self._proc:
            return

        try:
            if self._proc.poll() is None:
                self._proc.terminate()
                try:
                    self._proc.wait(timeout=1.5)
                except Exception:
                    self._proc.kill()
        except Exception:
            pass
        finally:
            self._proc = None