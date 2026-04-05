from __future__ import annotations

import re
import shutil
import subprocess
import threading
from typing import Any, Optional

from backEnd.models.events import host_seen, traffic_seen
from backEnd.models.types import event_meta, sensor_source, protocol, confidence_level
from backEnd.utils.logging import get_logger
from backEnd.utils.net import (
    normalize_ip,
    normalize_mac,
    detect_interface_ipv4,
    detect_interface_mac,
)


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

    # Match IPv4 flow tuple in both tcpdump formats:
    # - without -e: "IP 192.168.1.10.5353 > 224.0.0.251.5353: UDP, length 123"
    # - with -e: "... ethertype IPv4 ..., length 98: 192.168.1.10.5353 > 224.0.0.251.5353: ..."
    _ip_line_re = re.compile(
        r"(?P<src_ip>\d+\.\d+\.\d+\.\d+)(?:\.(?P<src_port>\d+))?\s+>\s+"
        r"(?P<dst_ip>\d+\.\d+\.\d+\.\d+)(?:\.(?P<dst_port>\d+))?\b"
    )

    # Example with tcpdump -e:
    # aa:bb:cc:dd:ee:ff > 11:22:33:44:55:66, ethertype ...
    _mac_pair_re = re.compile(
        r"(?P<src_mac>(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2})\s*>\s*"
        r"(?P<dst_mac>(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2})"
    )

    # Example ARP line:
    # ARP, Request who-has 192.168.1.1 tell 192.168.1.10, length 28
    _arp_who_has_re = re.compile(
        r"\bARP.*who-has\s+(?P<target_ip>\d+\.\d+\.\d+\.\d+)\s+tell\s+(?P<src_ip>\d+\.\d+\.\d+\.\d+)\b",
        re.IGNORECASE,
    )
    _arp_reply_re = re.compile(
        r"\bARP,\s*Reply\s+"
        r"(?P<src_ip>\d+\.\d+\.\d+\.\d+)\s+is-at\s+"
        r"(?P<src_mac>(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2})"
        r"(?:.*\bfor\s+(?P<dst_ip>\d+\.\d+\.\d+\.\d+))?\b",
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
        self._local_ip: str | None = None
        self._local_mac: str | None = None

        iface = getattr(cfg, "interface", None)
        if iface:
            try:
                self._local_ip = detect_interface_ipv4(iface)
            except Exception:
                self._local_ip = None
            try:
                self._local_mac = detect_interface_mac(iface)
            except Exception:
                self._local_mac = None

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
                "-e",   # include link-layer headers (MAC addresses)
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
                "-e", "eth.src",
                "-e", "eth.dst",
                "-e", "arp.src.hw_mac",
                "-e", "arp.dst.hw_mac",
                "-e", "arp.opcode",
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
        src_mac, dst_mac = self._extract_mac_pair(line)

        # ARP reply -> host_seen (+ ARP traffic edge when destination is known)
        arp_reply_match = self._arp_reply_re.search(line)
        if arp_reply_match:
            try:
                src_ip = normalize_ip(arp_reply_match.group("src_ip"))
            except ValueError:
                src_ip = None

            if src_ip:
                dst_ip_raw = arp_reply_match.group("dst_ip")
                inferred_dst_ip: str | None = None
                if dst_ip_raw:
                    try:
                        inferred_dst_ip = normalize_ip(dst_ip_raw)
                    except ValueError:
                        inferred_dst_ip = None
                elif (
                    self._local_ip
                    and self._local_mac
                    and dst_mac
                    and dst_mac == self._local_mac
                ):
                    inferred_dst_ip = self._local_ip

                reply_src_mac = self._normalize_capture_mac(arp_reply_match.group("src_mac")) or src_mac

                meta = event_meta(
                    source=sensor_source.tcpdump,
                    iface=iface,
                    confidence=confidence_level.medium,
                )

                self._bus.publish(host_seen(meta=meta, ip=src_ip, mac=reply_src_mac))

                if inferred_dst_ip:
                    self._bus.publish(host_seen(meta=meta, ip=inferred_dst_ip))
                    packet_bytes = self._extract_length_from_tcpdump(line)
                    self._bus.publish(
                        traffic_seen(
                            meta=meta,
                            src_ip=src_ip,
                            dst_ip=inferred_dst_ip,
                            proto=protocol.arp,
                            src_port=None,
                            dst_port=None,
                            bytes=packet_bytes,
                        )
                    )
                return

        # ARP request -> host_seen(source only)
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

            self._bus.publish(host_seen(meta=meta, ip=src_ip, mac=src_mac))

            # Emit ARP relationship as traffic so topology edges can appear
            # for hosts first seen via ARP probes.
            packet_bytes = self._extract_length_from_tcpdump(line)
            self._bus.publish(
                traffic_seen(
                    meta=meta,
                    src_ip=src_ip,
                    dst_ip=target_ip,
                    proto=protocol.arp,
                    src_port=None,
                    dst_port=None,
                    bytes=packet_bytes,
                )
            )
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
          10 eth.src
          11 eth.dst
          12 arp.src.hw_mac
          13 arp.dst.hw_mac
          14 arp.opcode
        """
        parts = line.split("|")
        if len(parts) < 10:
            return

        def _part(index: int) -> str:
            if index >= len(parts):
                return ""
            return parts[index].strip()

        protocols_field = _part(0)
        ip_src = _part(1)
        ip_dst = _part(2)
        tcp_src = _part(3)
        tcp_dst = _part(4)
        udp_src = _part(5)
        udp_dst = _part(6)
        arp_src = _part(7)
        arp_dst = _part(8)
        frame_len = _part(9)
        eth_src = self._normalize_capture_mac(_part(10))
        eth_dst = self._normalize_capture_mac(_part(11))
        arp_src_mac = self._normalize_capture_mac(_part(12))
        arp_dst_mac = self._normalize_capture_mac(_part(13))
        arp_opcode = _part(14)

        # ARP -> host_seen (+ optional ARP traffic edge when both endpoints are present)
        arp_src_ip: str | None = None
        arp_dst_ip: str | None = None
        is_arp_reply = (
            arp_opcode in {"2", "reply"}
            or (
                not arp_opcode
                and self._is_usable_mac(arp_dst_mac or eth_dst)
            )
        )
        if arp_src or arp_dst:
            try:
                if arp_src:
                    src_ip = normalize_ip(arp_src)
                    arp_src_ip = src_ip
                    self._bus.publish(
                        host_seen(
                            meta=event_meta(
                                source=sensor_source.tcpdump,
                                iface=iface,
                                confidence=confidence_level.medium,
                            ),
                            ip=src_ip,
                            mac=arp_src_mac or eth_src,
                        )
                    )

                if arp_dst:
                    dst_ip = normalize_ip(arp_dst)
                    arp_dst_ip = dst_ip
                    if is_arp_reply:
                        self._bus.publish(
                            host_seen(
                                meta=event_meta(
                                    source=sensor_source.tcpdump,
                                    iface=iface,
                                    confidence=confidence_level.medium,
                                ),
                                ip=dst_ip,
                                mac=(arp_dst_mac or eth_dst) if self._is_usable_mac(arp_dst_mac or eth_dst) else None,
                            )
                        )
            except ValueError:
                pass

            if (
                arp_src_ip
                and not arp_dst_ip
                and self._local_ip
                and self._local_mac
                and eth_dst
                and eth_dst == self._local_mac
            ):
                arp_dst_ip = self._local_ip
                self._bus.publish(
                    host_seen(
                        meta=event_meta(
                            source=sensor_source.tcpdump,
                            iface=iface,
                            confidence=confidence_level.medium,
                        ),
                        ip=arp_dst_ip,
                    )
                )

            if arp_src_ip and arp_dst_ip:
                packet_bytes = 0
                try:
                    if frame_len:
                        packet_bytes = int(frame_len)
                except Exception:
                    packet_bytes = 0

                self._bus.publish(
                    traffic_seen(
                        meta=event_meta(
                            source=sensor_source.tcpdump,
                            iface=iface,
                            confidence=confidence_level.medium,
                        ),
                        src_ip=arp_src_ip,
                        dst_ip=arp_dst_ip,
                        proto=protocol.arp,
                        src_port=None,
                        dst_port=None,
                        bytes=packet_bytes,
                    )
                )

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

    def _extract_mac_pair(self, line: str) -> tuple[str | None, str | None]:
        match = self._mac_pair_re.search(line)
        if not match:
            return None, None

        src = self._normalize_capture_mac(match.group("src_mac"))
        dst = self._normalize_capture_mac(match.group("dst_mac"))
        return src, dst

    def _normalize_capture_mac(self, value: str | None) -> str | None:
        if not value:
            return None

        try:
            return normalize_mac(value)
        except Exception:
            return None

    def _is_usable_mac(self, mac: str | None) -> bool:
        if not mac:
            return False
        if mac == "00:00:00:00:00:00":
            return False
        if mac == "ff:ff:ff:ff:ff:ff":
            return False
        return True

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
