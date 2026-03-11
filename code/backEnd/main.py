# code/backEnd/main.py

from __future__ import annotations

import threading
import time
import json
from pathlib import Path

from backEnd.pipeline.event_bus import event_bus
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
from backEnd.utils.net import detect_interface_network_cidr
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

    if not session.get_discovery_target_cidr():
        resolved_cidr = detect_interface_network_cidr(interface)
        session.set_discovery_target_cidr(resolved_cidr)

    log.info(f"Discovery CIDR: {session.get_discovery_target_cidr()}")

    stop_event = threading.Event()

    bus = event_bus(per_subscriber_max_size=10000, drop_if_full=True)
    sub = bus.subscribe("main")

    mongo = mongo_client_manager(session_cfg)

    try:
        mongo.connect()
        log.info("Mongo client connected.")

        # Backend is now considered ready
        write_ready_flag()

    except Exception as exc:
        log.error(f"Mongo connection failed: {exc}")
        return

    store = librarian(mongo)

    event_extractor = extractor()
    event_enricher = enricher(session_cfg)
    event_correlator = correlator(store)

    passive_thread: passive_listener | None = None

    last_interval_scan_ts = 0.0
    targeted_last_scan_ts: dict[str, float] = {}

    try:
        while not stop_event.is_set():

            if shutdown_requested():
                log.info("Shutdown flag detected. Beginning graceful shutdown...")
                break

            now = time.time()

            # -------------------------------------------------
            # Passive listener dynamic control
            # -------------------------------------------------

            passive_enabled = session.get_enable_passive_listener()

            if passive_enabled and passive_thread is None:

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

            # -------------------------------------------------
            # Active discovery interval
            # -------------------------------------------------

            if session.get_enable_active_discovery():

                interval_seconds = session.get_discovery_interval_seconds()

                if interval_seconds > 0 and now - last_interval_scan_ts >= interval_seconds:

                    target = session.get_discovery_target_cidr()

                    log.info(f"Running interval discovery: target={target}")

                    run_discovery(session_cfg, bus, target=target)

                    last_interval_scan_ts = now

                    if shutdown_requested():
                        log.info("Shutdown flag detected after interval discovery.")
                        break

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

                if session.get_enable_active_discovery() and signals.targeted_scan_ip:

                    ip = signals.targeted_scan_ip.strip()

                    if ip:

                        cooldown_seconds = session.get_targeted_scan_cooldown_seconds()

                        last = targeted_last_scan_ts.get(ip, 0.0)

                        if now - last >= cooldown_seconds:

                            log.info(f"Running targeted discovery: ip={ip}")

                            run_discovery(session_cfg, bus, target=ip)

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
            mongo.close()
        except Exception:
            pass

        log.info("NetTower backend stopped.")


if __name__ == "__main__":

    main()