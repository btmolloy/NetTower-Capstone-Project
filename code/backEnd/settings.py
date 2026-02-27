#Purpose: Collect user input (CLI for now), validate it using utils/net.py, and produce config overrides.
#Inputs: CLI args / environment variables (and later UI settings).
#Outputs: Parsed + validated values that feed into Config.

from __future__ import annotations

import argparse

from backEnd.config import config
from backEnd.utils.net import (
    is_valid_cidr,
    is_valid_interface,
    normalize_cidr,
)
from backEnd.utils.logging import get_logger


def load_config_from_cli() -> config:
    """
    Build a config object using:
      - defaults
      - environment overrides (config.from_env)
      - CLI overrides (this file)
    """
    base_cfg = config.from_env()
    log = get_logger("backEnd.settings", base_cfg.log_level, base_cfg.log_file)

    parser = argparse.ArgumentParser(prog="nettower", add_help=True)

    parser.add_argument("--interface", dest="interface", help="capture interface (e.g. eth0)")
    parser.add_argument("--cidr", dest="discovery_target_cidr", help="discovery target CIDR (e.g. 192.168.1.0/24)")
    parser.add_argument("--interval", dest="discovery_interval_seconds", type=int, help="interval discovery seconds")
    parser.add_argument("--cooldown", dest="targeted_scan_cooldown_seconds", type=int, help="targeted scan cooldown seconds")

    parser.add_argument("--mongo-uri", dest="mongo_uri", help="mongodb uri")
    parser.add_argument("--mongo-db", dest="mongo_db_name", help="mongodb db name")

    parser.add_argument("--enable-passive", dest="enable_passive_listener", action="store_true")
    parser.add_argument("--disable-passive", dest="enable_passive_listener", action="store_false")
    parser.set_defaults(enable_passive_listener=base_cfg.enable_passive_listener)

    parser.add_argument("--enable-active", dest="enable_active_discovery", action="store_true")
    parser.add_argument("--disable-active", dest="enable_active_discovery", action="store_false")
    parser.set_defaults(enable_active_discovery=base_cfg.enable_active_discovery)

    parser.add_argument("--enable-nmap", dest="enable_nmap", action="store_true")
    parser.add_argument("--disable-nmap", dest="enable_nmap", action="store_false")
    parser.set_defaults(enable_nmap=False)

    parser.add_argument("--nmap-ports", dest="nmap_ports", default=None, help="ports list for nmap (e.g. 22,80,443)")

    args = parser.parse_args()

    # Start with base env config, then override selectively
    cfg_dict = base_cfg.__dict__.copy()

    if args.interface:
        iface = args.interface.strip()
        if not is_valid_interface(iface):
            raise ValueError(f"invalid interface: {iface}")
        cfg_dict["interface"] = iface

    if args.discovery_target_cidr:
        cidr = args.discovery_target_cidr.strip()
        if not is_valid_cidr(cidr):
            raise ValueError(f"invalid cidr: {cidr}")
        cfg_dict["discovery_target_cidr"] = normalize_cidr(cidr)

    if args.discovery_interval_seconds is not None:
        if args.discovery_interval_seconds <= 0:
            raise ValueError("discovery interval must be > 0")
        cfg_dict["discovery_interval_seconds"] = int(args.discovery_interval_seconds)

    if args.targeted_scan_cooldown_seconds is not None:
        if args.targeted_scan_cooldown_seconds < 0:
            raise ValueError("cooldown must be >= 0")
        cfg_dict["targeted_scan_cooldown_seconds"] = int(args.targeted_scan_cooldown_seconds)

    if args.mongo_uri:
        cfg_dict["mongo_uri"] = args.mongo_uri.strip()

    if args.mongo_db_name:
        cfg_dict["mongo_db_name"] = args.mongo_db_name.strip()

    cfg_dict["enable_passive_listener"] = bool(args.enable_passive_listener)
    cfg_dict["enable_active_discovery"] = bool(args.enable_active_discovery)

    # settings.py can attach extra fields for active discovery without forcing config changes yet
    cfg_dict["enable_nmap"] = bool(args.enable_nmap)
    if args.nmap_ports:
        cfg_dict["nmap_ports"] = args.nmap_ports.strip()

    final_cfg = config(**cfg_dict)  # type: ignore[arg-type]
    log.info(
        f"config loaded: iface={final_cfg.interface} cidr={final_cfg.discovery_target_cidr} "
        f"interval={final_cfg.discovery_interval_seconds}s passive={final_cfg.enable_passive_listener} "
        f"active={final_cfg.enable_active_discovery}"
    )

    return final_cfg