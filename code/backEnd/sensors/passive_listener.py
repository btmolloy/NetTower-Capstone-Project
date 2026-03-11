from __future__ import annotations

import re
import shutil
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

    Starts a packet capture backend and publishes packet-derived events
    to the event_bus. Focus is topology/activity, NOT payload reconstruction.

    Cross-platform approach:
      - Prefer tcpdump when available
      - Fall back to tshark when available
      - If neither exists, disable passive capture cleanly
    """

    # Example tcpdump IPv4 line:
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

    _length_re = re.compile(r"\blength\s+(?P<length>\d+)\b", re.IGNORECASE)

    def __init__(self, cfg: Any, bus: Any, stop_event: threading.Event) -> None:
        super().__init__(daemon=True)
        self._cfg = cfg
        self._bus = bus
        self._stop_event = stop_event
        self._log = get_logger(
            "backEnd.sensors.passive_listener",
            getattr(cfg, "log_level", "INFO"),
            getattr(cfg, "log_file", None),
        )

        self._proc: Optional[subprocess.Popen[str]] = None
        self._capture_backend: Optional[str] = None
        self._last_stderr_line: Optional[str] = None

    def run(self) -> None:
        iface = getattr(self._cfg, "interface", None)
        bpf_filter = getattr(self._cfg, "passive_bpf_filter", "arp or ip")

        if not iface:
            self._log.error("No capture interface resolved. Passive listener disabled.")
            return

        cmd = self._build_capture_command(iface, bpf_filter)
        if not cmd:
            self._log.error(
                "No supported packet capture backend found (tcpdump/tshark). Passive listener disabled."
            )
            return

        self._log.info(
            f"Starting passive capture backend={self._capture_backend} iface={iface} "
            f"filter='{bpf_filter}' cmd={cmd}"
        )

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except Exception as exc:
            self._log.error(f"Failed to start passive capture backend: {exc}")
            return

        stderr_thread = threading.Thread(
            target=self._drain_stderr,
            name="passive-listener-stderr",
            daemon=True,
        )
        stderr_thread.start()

        self._log.info(
            f"passive listener started on iface={iface} "
            f"backend={self._capture_backend} filter='{bpf_filter}'"
        )

        unexpected_exit = False
        exit_code: int | None = None

        try:
            assert self._proc.stdout is not None

            while not self._stop_event.is_set():
                line = self._proc.stdout.readline()

                if not line:
                    if self._proc.poll() is not None:
                        unexpected_exit = True
                        exit_code = self._proc.poll()
                        break
                    continue

                line = line.strip()
                if not line:
                    continue

                if self._capture_backend == "tcpdump":
                    self._handle_tcpdump_line(line, iface)
                elif self._capture_backend == "tshark":
                    self._handle_tshark_line(line, iface)

        except Exception:
            self._log.exception("Fatal error in passive listener loop")
        finally:
            if unexpected_exit:
                if self._last_stderr_line:
                    self._log.error(
                        f"Passive capture backend exited unexpectedly "
                        f"(backend={self._capture_backend}, iface={iface}, exit_code={exit_code}). "
                        f"Last stderr: {self._last_stderr_line}"
                    )
                else:
                    self._log.error(
                        f"Passive capture backend exited unexpectedly "
                        f"(backend={self._capture_backend}, iface={iface}, exit_code={exit_code})."
                    )

            self._shutdown_proc()

            if self._stop_event.is_set():
                self._log.info("passive listener stopped")
            else:
                self._log.warning("passive listener stopped")

    def _build_capture_command(self, iface: str, bpf_filter: str) -> list[str] | None:
        """
        Build the passive capture command.

        tcpdump:
          Good fit on macOS/Linux

        tshark:
          Better cross-platform option, especially on Windows
        """
        tcpdump_path = shutil.which("tcpdump")
        if tcpdump_path:
            self._capture_backend = "tcpdump"
            return [
                tcpdump_path,
                "-l",   # line-buffered
                "-n",   # no name resolution
                "-i", iface,
                bpf_filter,
            ]

        tshark_path = shutil.which("tshark")
        if tshark_path:
            self._capture_backend = "tshark"
            return [
                tshark_path,
                "-l",
                "-n",
                "-i", iface,
                "-f", bpf_filter,
                "-Y", "arp or ip",
                "-T", "fields",
                "-E", "separator=|",
                "-E", "occurrence=f",
                "-e", "frame.protocols",
                "-e", "ip.src",
                "-e", "ip.dst",
                "-e", "tcp.srcport",
                "-e", "tcp.dstport",
                "-e", "udp.srcport",
                "-e", "udp.dstport",
                "-e", "arp.src.proto_ipv4",
                "-e", "arp.dst.proto_ipv4",
                "-e", "frame.len",
            ]

        return None

    def _drain_stderr(self) -> None:
        """
        Drain stderr so the subprocess does not block and so we retain the
        most recent useful error line for debugging.
        """
        if self._proc is None or self._proc.stderr is None:
            return

        try:
            while True:
                line = self._proc.stderr.readline()
                if not line:
                    if self._proc.poll() is not None:
                        break
                    continue

                line = line.strip()
                if not line:
                    continue

                self._last_stderr_line = line
                self._log.warning(f"{self._capture_backend} stderr: {line}")
        except Exception:
            self._log.exception("Failed while reading passive capture stderr")

    def _handle_tcpdump_line(self, line: str, iface: str) -> None:
        # ARP -> host_seen
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
            packet_bytes = self._extract_length_from_tcpdump(line)

            meta = event_meta(
                source=sensor_source.tcpdump,
                iface=iface,
                confidence=confidence_level.low,
            )

            proto_enum = self._infer_proto_from_tcpdump_line(line, src_port, dst_port)

            event = traffic_seen(
                meta=meta,
                src_ip=src_ip,
                dst_ip=dst_ip,
                proto=proto_enum,
                src_port=int(src_port) if src_port else None,
                dst_port=int(dst_port) if dst_port else None,
                bytes=packet_bytes,
            )
            self._bus.publish(event)

    def _handle_tshark_line(self, line: str, iface: str) -> None:
        """
        Expected tshark field order:
          0 frame.protocols
          1 ip.src
          2 ip.dst
          3 tcp.srcport
          4 tcp.dstport
          5 udp.srcport
          6 udp.dstport
          7 arp.src.proto_ipv4
          8 arp.dst.proto_ipv4
          9 frame.len
        """
        parts = line.split("|")
        if len(parts) < 10:
            return

        protocols_field = parts[0].strip()
        ip_src = parts[1].strip()
        ip_dst = parts[2].strip()
        tcp_src = parts[3].strip()
        tcp_dst = parts[4].strip()
        udp_src = parts[5].strip()
        udp_dst = parts[6].strip()
        arp_src = parts[7].strip()
        arp_dst = parts[8].strip()
        frame_len = parts[9].strip()

        # ARP -> host_seen
        if arp_src or arp_dst:
            try:
                if arp_src:
                    src_ip = normalize_ip(arp_src)
                    self._bus.publish(
                        host_seen(
                            meta=event_meta(
                                source=sensor_source.tcpdump,
                                iface=iface,
                                confidence=confidence_level.medium,
                            ),
                            ip=src_ip,
                        )
                    )

                if arp_dst:
                    dst_ip = normalize_ip(arp_dst)
                    self._bus.publish(
                        host_seen(
                            meta=event_meta(
                                source=sensor_source.tcpdump,
                                iface=iface,
                                confidence=confidence_level.medium,
                            ),
                            ip=dst_ip,
                        )
                    )
            except ValueError:
                pass

        # IP traffic -> traffic_seen
        if ip_src and ip_dst:
            try:
                src_ip = normalize_ip(ip_src)
                dst_ip = normalize_ip(ip_dst)
            except ValueError:
                return

            src_port: int | None = None
            dst_port: int | None = None
            proto_enum = protocol.tcp

            if tcp_src or tcp_dst:
                proto_enum = protocol.tcp
                src_port = int(tcp_src) if tcp_src else None
                dst_port = int(tcp_dst) if tcp_dst else None
            elif udp_src or udp_dst:
                proto_enum = protocol.udp
                src_port = int(udp_src) if udp_src else None
                dst_port = int(udp_dst) if udp_dst else None
            elif "icmp" in protocols_field.lower():
                proto_enum = protocol.icmp

            packet_bytes = 0
            try:
                if frame_len:
                    packet_bytes = int(frame_len)
            except Exception:
                packet_bytes = 0

            meta = event_meta(
                source=sensor_source.tcpdump,
                iface=iface,
                confidence=confidence_level.low,
            )

            self._bus.publish(
                traffic_seen(
                    meta=meta,
                    src_ip=src_ip,
                    dst_ip=dst_ip,
                    proto=proto_enum,
                    src_port=src_port,
                    dst_port=dst_port,
                    bytes=packet_bytes,
                )
            )

    def _infer_proto_from_tcpdump_line(
        self,
        line: str,
        src_port: str | None,
        dst_port: str | None,
    ) -> protocol:
        upper_line = line.upper()

        if "ICMP" in upper_line:
            return protocol.icmp
        if "UDP" in upper_line:
            return protocol.udp
        if "TCP" in upper_line:
            return protocol.tcp

        if src_port or dst_port:
            return protocol.tcp

        return protocol.icmp

    def _extract_length_from_tcpdump(self, line: str) -> int:
        match = self._length_re.search(line)
        if not match:
            return 0

        try:
            return int(match.group("length"))
        except Exception:
            return 0

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
                    try:
                        self._proc.wait(timeout=1.0)
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            self._proc = None