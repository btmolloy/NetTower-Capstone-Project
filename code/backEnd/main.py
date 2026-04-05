# code/backEnd/main.py

from __future__ import annotations

import concurrent.futures
import threading
import time
import json
from pathlib import Path

from backEnd.pipeline.event_bus import event_bus
from backEnd.models.events import host_seen
from backEnd.models.types import event_meta, sensor_source, confidence_level
from backEnd.processors.correlation import correlator
from backEnd.processors.enrichment import enricher
from backEnd.processors.extractors import extractor
from backEnd.runtime.session_manager import SessionManager
from backEnd.runtime.session_config import SessionConfig
from backEnd.runtime.shutdown import shutdown_requested, clear_shutdown_flag
from backEnd.sensors.active_discovery import run_discovery
from backEnd.sensors.passive_listener import passive_listener
from backEnd.storage.librarian import librarian
from backEnd.storage.mongo_client import mongo_client_manager
from backEnd.utils.logging import get_logger
from backEnd.utils.net import (
    detect_interface_network_cidr,
    detect_interface_ipv4,
    detect_interface_mac,
    is_private_rfc1918_cidr,
    is_private_rfc1918_ipv4,
)
from backEnd.runtime.runtime_state import write_ready_flag, clear_ready_flag


def load_session_config() -> SessionConfig:
    """
    Load SessionConfig written by the runtime supervisor.
    """

    runtime_dir = Path(__file__).resolve().parents[1] / "runtime"
    session_file = runtime_dir / "session_config.json"

    if not session_file.exists():
        raise RuntimeError("Session configuration file not found")

    with open(session_file) as f:
        data = json.load(f)

    return SessionConfig.from_dict(data)


def apply_runtime_session_updates(session: SessionManager, log) -> None:
    """
    Apply runtime session updates written by the frontend bridge.
    """

    runtime_dir = Path(__file__).resolve().parents[1] / "runtime"
    update_file = runtime_dir / "session_update.json"

    if not update_file.exists():
        return

    try:
        with open(update_file, encoding="utf-8") as f:
            updates = json.load(f)
    except Exception as exc:
        log.warning(f"Ignoring invalid runtime session update: {exc}")
        try:
            update_file.unlink(missing_ok=True)
        except Exception:
            pass
        return

    try:
        if "enable_active_discovery" in updates:
            session.set_enable_active_discovery(bool(updates["enable_active_discovery"]))
            log.info(
                "Runtime update: enable_active_discovery="
                f"{session.get_enable_active_discovery()}"
            )

        if "allow_all_active_targets" in updates:
            session.set_allow_all_active_targets(bool(updates["allow_all_active_targets"]))
            log.info(
                "Runtime update: allow_all_active_targets="
                f"{session.get_allow_all_active_targets()}"
            )

        if "enable_icmp_scan" in updates:
            session.set_enable_icmp_scan(bool(updates["enable_icmp_scan"]))
            log.info(
                "Runtime update: enable_icmp_scan="
                f"{session.get_enable_icmp_scan()}"
            )

        if "enable_nmap_scan" in updates:
            session.set_enable_nmap_scan(bool(updates["enable_nmap_scan"]))
            log.info(
                "Runtime update: enable_nmap_scan="
                f"{session.get_enable_nmap_scan()}"
            )

        if "discovery_target_cidr" in updates:
            cidr_value = updates.get("discovery_target_cidr")
            if cidr_value is not None:
                cidr_value = str(cidr_value).strip()
                if cidr_value == "":
                    cidr_value = None
            session.set_discovery_target_cidr(cidr_value)
            log.info(
                "Runtime update: discovery_target_cidr="
                f"{session.get_discovery_target_cidr()}"
            )
    finally:
        try:
            update_file.unlink(missing_ok=True)
        except Exception:
            pass


def main() -> None:
    """
    Backend runtime entry point.

    Mongo lifecycle is controlled by the supervisor.
    SessionConfig defines initial scan behavior.
    """

    # Clear any stale runtime flags (e.g., after crash)
    clear_ready_flag()
    clear_shutdown_flag()

    session_cfg = load_session_config()
    session = SessionManager(session_cfg)

    log = get_logger("backEnd.main", "INFO", None)

    log.info("NetTower backend starting...")

    interface = session.get_interface()

    log.info(f"Interface: {interface}")

    local_network_cidr: str | None = None
    try:
        local_network_cidr = detect_interface_network_cidr(interface)
    except Exception as exc:
        log.warning(f"Unable to determine local network CIDR: {exc}")

    if not session.get_discovery_target_cidr() and local_network_cidr:
        session.set_discovery_target_cidr(local_network_cidr)

    log.info(f"Discovery CIDR: {session.get_discovery_target_cidr()}")
    log.info(
        "Active discovery scope: "
        f"{'all targets' if session.get_allow_all_active_targets() else 'private-only (RFC1918)'}"
    )
    log.info(
        "Active discovery methods: "
        f"icmp={session.get_enable_icmp_scan()} nmap={session.get_enable_nmap_scan()}"
    )

    stop_event = threading.Event()

    bus = event_bus(per_subscriber_max_size=10000, drop_if_full=True)
    sub = bus.subscribe("main")

    mongo = mongo_client_manager(session_cfg)

    try:
        mongo.connect()
        log.info("Mongo client connected.")

        # Hard-reset topology collections at the beginning of every session.
        # This guarantees the UI starts from clean state each app run.
        handles = mongo.handles()
        deleted_hosts = handles.hosts.delete_many({}).deleted_count
        deleted_edges = handles.edges.delete_many({}).deleted_count
        log.info(
            "Cleared Mongo collections for new session: "
            f"hosts={deleted_hosts}, edges={deleted_edges}"
        )

        # Backend is now considered ready
        write_ready_flag()

    except Exception as exc:
        log.error(f"Mongo connection failed: {exc}")
        return

    store = librarian(mongo)

    event_extractor = extractor()
    event_enricher = enricher(session_cfg)
    event_correlator = correlator(store)

    local_ip_for_heartbeat: str | None = None
    local_mac_for_heartbeat: str | None = None

    # Seed topology with the local interface host so UI has immediate context.
    try:
        local_ip = detect_interface_ipv4(interface)
        local_mac = None
        try:
            local_mac = detect_interface_mac(interface)
        except Exception:
            local_mac = None

        bootstrap_event = host_seen(
            meta=event_meta(
                source=sensor_source.ping,
                iface=interface,
                confidence=confidence_level.high,
            ),
            ip=local_ip,
            mac=local_mac,
        )
        bootstrap_event, bootstrap_enrichment = event_enricher.enrich(bootstrap_event)
        host_updates, edge_updates, _ = event_correlator.process(
            bootstrap_event,
            bootstrap_enrichment,
        )
        for host in host_updates:
            store.upsert_host(host)
        for edge in edge_updates:
            store.upsert_edge(edge)
        local_ip_for_heartbeat = local_ip
        local_mac_for_heartbeat = local_mac
        log.info(f"Seeded local host into topology: {local_ip}")
    except Exception as exc:
        log.warning(f"Unable to seed local host into topology: {exc}")

    passive_thread: passive_listener | None = None
    active_interval_thread: threading.Thread | None = None
    targeted_scan_executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=4,
        thread_name_prefix="active-targeted-discovery",
    )
    targeted_scan_futures: dict[str, concurrent.futures.Future] = {}
    max_pending_targeted_jobs = 128
    passive_restart_cooldown_seconds = 5.0
    passive_next_restart_not_before = 0.0

    last_interval_scan_ts = 0.0
    targeted_last_scan_ts: dict[str, float] = {}
    local_heartbeat_interval_seconds = 10.0
    next_local_heartbeat_ts = 0.0
    active_methods_disabled_logged = False

    try:
        while not stop_event.is_set():

            completed_targeted_ips: list[str] = []
            for target_ip, future in targeted_scan_futures.items():
                if not future.done():
                    continue
                completed_targeted_ips.append(target_ip)
                try:
                    future.result()
                except Exception:
                    log.exception(f"Targeted discovery task failed: ip={target_ip}")
            for target_ip in completed_targeted_ips:
                targeted_scan_futures.pop(target_ip, None)

            if shutdown_requested():
                log.info("Shutdown flag detected. Beginning graceful shutdown...")
                break

            now = time.time()

            if local_ip_for_heartbeat and now >= next_local_heartbeat_ts:
                try:
                    heartbeat_event = host_seen(
                        meta=event_meta(
                            source=sensor_source.ping,
                            iface=interface,
                            confidence=confidence_level.high,
                        ),
                        ip=local_ip_for_heartbeat,
                        mac=local_mac_for_heartbeat,
                    )
                    heartbeat_event, heartbeat_enrichment = event_enricher.enrich(heartbeat_event)
                    host_updates, edge_updates, _ = event_correlator.process(
                        heartbeat_event,
                        heartbeat_enrichment,
                    )
                    for host in host_updates:
                        store.upsert_host(host)
                    for edge in edge_updates:
                        store.upsert_edge(edge)
                except Exception:
                    log.exception("Failed local host heartbeat update")
                finally:
                    next_local_heartbeat_ts = now + local_heartbeat_interval_seconds

            # -------------------------------------------------
            # Runtime session updates
            # -------------------------------------------------

            apply_runtime_session_updates(session, log)

            # -------------------------------------------------
            # Passive listener dynamic control
            # -------------------------------------------------

            passive_enabled = session.get_enable_passive_listener()

            # If the passive thread exited (e.g., permissions/backend capture error),
            # reset state so the runtime can retry and produce visible diagnostics.
            if passive_thread is not None and not passive_thread.is_alive():
                log.warning(
                    "Passive listener thread exited unexpectedly; "
                    f"retrying in {passive_restart_cooldown_seconds:.0f}s"
                )
                passive_thread = None
                passive_next_restart_not_before = now + passive_restart_cooldown_seconds

            if passive_enabled and passive_thread is None:
                if now >= passive_next_restart_not_before:
                    passive_thread = passive_listener(session_cfg, bus, stop_event)
                    passive_thread.start()
                    log.info("Passive listener started")

            if not passive_enabled and passive_thread is not None:

                log.info("Stopping passive listener")

                stop_event.set()

                passive_thread.join(timeout=2.0)
                passive_thread = None

                stop_event.clear()

                if shutdown_requested():
                    log.info("Shutdown flag detected during passive listener shutdown.")
                    break

            if not passive_enabled:
                passive_next_restart_not_before = 0.0

            # -------------------------------------------------
            # Active discovery interval
            # -------------------------------------------------

            if session.get_enable_active_discovery():
                icmp_scan_enabled = session.get_enable_icmp_scan()
                nmap_scan_enabled = session.get_enable_nmap_scan()
                if not (icmp_scan_enabled or nmap_scan_enabled):
                    if not active_methods_disabled_logged:
                        log.info(
                            "Active sensor is enabled but both ICMP and NMAP scans are disabled; "
                            "skipping active discovery."
                        )
                        active_methods_disabled_logged = True
                else:
                    active_methods_disabled_logged = False

                    interval_seconds = session.get_discovery_interval_seconds()

                    if interval_seconds > 0 and now - last_interval_scan_ts >= interval_seconds:

                        target = session.get_discovery_target_cidr()
                        allow_all_targets = session.get_allow_all_active_targets()
                        if not allow_all_targets:
                            if target and not is_private_rfc1918_cidr(target):
                                target = None
                            if not target:
                                if local_network_cidr and is_private_rfc1918_cidr(local_network_cidr):
                                    target = local_network_cidr

                        if not target:
                            log.warning(
                                "Skipping interval discovery: private-only scope requires an "
                                "RFC1918 target CIDR, but none is available."
                            )
                        elif active_interval_thread is None or not active_interval_thread.is_alive():
                            log.info(f"Running interval discovery: target={target}")

                            def _run_interval_discovery() -> None:
                                try:
                                    run_discovery(
                                        session_cfg,
                                        bus,
                                        target=target,
                                        enable_icmp_scan=icmp_scan_enabled,
                                        enable_nmap_scan=nmap_scan_enabled,
                                    )
                                except Exception:
                                    log.exception("Interval discovery task failed")

                            active_interval_thread = threading.Thread(
                                target=_run_interval_discovery,
                                daemon=True,
                                name="active-interval-discovery",
                            )
                            active_interval_thread.start()
                        else:
                            log.info("Skipping interval discovery: previous interval scan still running")

                        last_interval_scan_ts = now

                        if shutdown_requested():
                            log.info("Shutdown flag detected after interval discovery.")
                            break
            else:
                active_methods_disabled_logged = False

            # -------------------------------------------------
            # Process pipeline events
            # -------------------------------------------------

            item = sub.get(timeout=0.5)

            if item is None:
                continue

            events = event_extractor.to_events(item)

            if not events:
                continue

            for ev in events:

                if shutdown_requested():
                    log.info("Shutdown flag detected during event processing.")
                    break

                ev, enrichment_data = event_enricher.enrich(ev)

                host_updates, edge_updates, signals = event_correlator.process(
                    ev,
                    enrichment_data,
                )

                for host in host_updates:
                    store.upsert_host(host)

                for edge in edge_updates:
                    store.upsert_edge(edge)

                # ---------------------------------------------
                # Targeted active discovery
                # ---------------------------------------------

                if (
                    session.get_enable_active_discovery()
                    and (session.get_enable_icmp_scan() or session.get_enable_nmap_scan())
                    and signals.targeted_scan_ip
                ):

                    ip = signals.targeted_scan_ip.strip()

                    if ip:
                        icmp_scan_enabled = session.get_enable_icmp_scan()
                        nmap_scan_enabled = session.get_enable_nmap_scan()
                        if not session.get_allow_all_active_targets():
                            try:
                                in_private_scope = is_private_rfc1918_ipv4(ip)
                            except Exception:
                                log.info(
                                    f"Skipping targeted discovery with invalid IP: ip={ip}"
                                )
                                continue

                            if not in_private_scope:
                                log.info(
                                    f"Skipping targeted discovery outside private scope: "
                                    f"ip={ip} scope=rfc1918"
                                )
                                continue

                        cooldown_seconds = session.get_targeted_scan_cooldown_seconds()

                        last = targeted_last_scan_ts.get(ip, 0.0)

                        if now - last >= cooldown_seconds:
                            if ip in targeted_scan_futures:
                                continue
                            if len(targeted_scan_futures) >= max_pending_targeted_jobs:
                                log.warning(
                                    "Skipping targeted discovery: pending queue is full "
                                    f"(pending={len(targeted_scan_futures)} cap={max_pending_targeted_jobs})"
                                )
                                continue

                            log.info(f"Scheduling targeted discovery: ip={ip}")
                            future = targeted_scan_executor.submit(
                                run_discovery,
                                session_cfg,
                                bus,
                                ip,
                                icmp_scan_enabled,
                                nmap_scan_enabled,
                            )
                            targeted_scan_futures[ip] = future
                            targeted_last_scan_ts[ip] = now

                            if shutdown_requested():
                                log.info("Shutdown flag detected after targeted discovery.")
                                break

            if shutdown_requested():
                break

    except KeyboardInterrupt:

        log.info("KeyboardInterrupt received, shutting down...")

    except Exception:

        log.exception("Fatal error in main loop")

    finally:

        # Remove ready flag on shutdown
        clear_ready_flag()

        # Acknowledge shutdown request if one was issued
        clear_shutdown_flag()

        stop_event.set()

        try:
            bus.close()
        except Exception:
            pass

        if passive_thread is not None:
            try:
                passive_thread.join(timeout=2.0)
            except Exception:
                pass

        try:
            targeted_scan_executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            targeted_scan_executor.shutdown(wait=False)
        except Exception:
            pass

        try:
            mongo.close()
        except Exception:
            pass

        log.info("NetTower backend stopped.")


if __name__ == "__main__":

    main()
