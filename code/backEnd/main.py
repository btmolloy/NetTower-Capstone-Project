# code/backEnd/main.py
from __future__ import annotations

from dataclasses import replace
import threading
import time
from typing import Any

from backEnd.pipeline.event_bus import event_bus
from backEnd.processors.correlation import correlator
from backEnd.processors.enrichment import enricher
from backEnd.processors.extractors import extractor
from backEnd.sensors.active_discovery import run_discovery
from backEnd.sensors.passive_listener import passive_listener
from backEnd.settings import load_config_from_cli
from backEnd.storage.librarian import librarian
from backEnd.storage.mongo_client import mongo_client_manager
from backEnd.storage.mongo_runtime import mongo_runtime_manager
from backEnd.utils.logging import get_logger
from backEnd.utils.net import detect_interface_network_cidr


def _safe_bool(val: Any, default: bool = False) -> bool:
    if isinstance(val, bool):
        return val
    return default


def main() -> None:
    cfg = load_config_from_cli()

    log = get_logger("backEnd.main", cfg.log_level, cfg.log_file)
    log.info("NetTower backend starting...")
    log.info(f"Resolved interface: {cfg.interface}")

    if not cfg.discovery_target_cidr:
        resolved_cidr = detect_interface_network_cidr(cfg.interface)
        cfg = replace(cfg, discovery_target_cidr=resolved_cidr)

    log.info(f"Resolved discovery target CIDR: {cfg.discovery_target_cidr}")

    stop_event = threading.Event()

    bus = event_bus(per_subscriber_max_size=10000, drop_if_full=True)
    sub = bus.subscribe("main")

    mongo_runtime = mongo_runtime_manager(cfg)
    mongo = mongo_client_manager(cfg)

    try:
        if cfg.mongo_auto_start:
            mongo_runtime.start()
            log.info("Local Mongo runtime started.")

        mongo.connect()
        log.info("Mongo client connected.")
    except Exception as exc:
        log.error(f"Mongo connection failed: {exc}")
        try:
            mongo_runtime.stop()
        except Exception:
            pass
        return

    store = librarian(mongo)

    event_extractor = extractor()
    event_enricher = enricher(cfg)
    event_correlator = correlator(store)

    passive_thread: passive_listener | None = None
    if cfg.enable_passive_listener:
        passive_thread = passive_listener(cfg, bus, stop_event)
        passive_thread.start()
        log.info("Passive listener enabled.")
    else:
        log.info("Passive listener disabled by config.")

    last_interval_scan_ts = 0.0
    targeted_last_scan_ts: dict[str, float] = {}

    interval_seconds = int(cfg.discovery_interval_seconds)
    cooldown_seconds = int(cfg.targeted_scan_cooldown_seconds)

    if cfg.enable_active_discovery:
        last_interval_scan_ts = 0.0

    try:
        while not stop_event.is_set():
            now = time.time()

            if cfg.enable_active_discovery and interval_seconds > 0:
                if now - last_interval_scan_ts >= interval_seconds:
                    target = cfg.discovery_target_cidr
                    log.info(f"Running interval discovery: target={target}")
                    run_discovery(cfg, bus, target=target)
                    last_interval_scan_ts = now

            item = sub.get(timeout=0.5)
            if item is None:
                continue

            events = event_extractor.to_events(item)
            if not events:
                continue

            for ev in events:
                ev, enrichment_data = event_enricher.enrich(ev)
                host_updates, edge_updates, signals = event_correlator.process(ev, enrichment_data)

                for host in host_updates:
                    store.upsert_host(host)

                for edge in edge_updates:
                    store.upsert_edge(edge)

                if cfg.enable_active_discovery and signals.targeted_scan_ip:
                    ip = signals.targeted_scan_ip.strip()
                    if ip:
                        last = targeted_last_scan_ts.get(ip, 0.0)
                        if now - last >= cooldown_seconds:
                            log.info(f"Running targeted discovery: ip={ip}")
                            run_discovery(cfg, bus, target=ip)
                            targeted_last_scan_ts[ip] = now

    except KeyboardInterrupt:
        log.info("KeyboardInterrupt received, shutting down...")
    except Exception:
        log.exception("Fatal error in main loop")
    finally:
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

        try:
            mongo_runtime.stop()
        except Exception:
            pass

        log.info("NetTower backend stopped.")


if __name__ == "__main__":
    main()