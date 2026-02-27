from __future__ import annotations

import json
import os
from typing import Any, Optional, Tuple

from backEnd.models.events import base_event, host_seen
from backEnd.utils.net import extract_oui
from backEnd.utils.logging import get_logger


class enricher:
    """
    Adds meaning to events using resources:

      - oui_vendors.json: OUI prefix -> vendor name
      - device_hints.json: vendor/oui/hostname keyword -> role/category

    Returns:
      (event, enrichment_dict)

    Does NOT:
      - modify DB
      - trigger scans
      - mutate event objects
    """

    def __init__(self, cfg: Any) -> None:
        self._cfg = cfg
        self._log = get_logger("backEnd.processors.enrichment", getattr(cfg, "log_level", "INFO"))

        base_dir = os.path.dirname(os.path.dirname(__file__))  # backEnd/
        resources_dir = os.path.join(base_dir, "resources")

        self._oui_path = os.path.join(resources_dir, "oui_vendors.json")
        self._hints_path = os.path.join(resources_dir, "device_hints.json")

        self._oui_vendors: dict[str, str] = {}
        self._device_hints: dict[str, Any] = {}

        self._load_resources()

    def _load_resources(self) -> None:
        self._oui_vendors = self._safe_load_json(self._oui_path, default={})
        self._device_hints = self._safe_load_json(self._hints_path, default={})

        # Normalize OUI keys to lowercase to avoid lookup misses
        self._oui_vendors = {k.lower(): v for k, v in self._oui_vendors.items() if isinstance(k, str)}

        oui_to_role = self._device_hints.get("oui_to_role", {})
        if isinstance(oui_to_role, dict):
            self._device_hints["oui_to_role"] = {k.lower(): v for k, v in oui_to_role.items() if isinstance(k, str)}

    def _safe_load_json(self, path: str, default: Any) -> Any:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            self._log.warning(f"resource not found: {path} (using defaults)")
            return default
        except json.JSONDecodeError as exc:
            self._log.warning(f"invalid json: {path} ({exc}) (using defaults)")
            return default
        except Exception as exc:
            self._log.warning(f"failed to load: {path} ({exc}) (using defaults)")
            return default

    def enrich(self, event: base_event) -> Tuple[base_event, dict[str, Any]]:
        """
        Return (event, enrichment_data).
        """
        enrichment_data: dict[str, Any] = {}

        # Only host_seen has mac/hostname fields right now
        if isinstance(event, host_seen):
            vendor = self._vendor_from_mac(event.mac)
            if vendor:
                enrichment_data["vendor"] = vendor

            role = self._role_hint(vendor=vendor, mac=event.mac, hostname=event.hostname)
            if role:
                enrichment_data["role_hint"] = role

        return event, enrichment_data

    def _vendor_from_mac(self, mac: Optional[str]) -> Optional[str]:
        if not mac:
            return None
        oui = extract_oui(mac)
        if not oui:
            return None
        return self._oui_vendors.get(oui.lower())

    def _role_hint(self, vendor: Optional[str], mac: Optional[str], hostname: Optional[str]) -> Optional[str]:
        # 1) OUI based
        oui = extract_oui(mac) if mac else None
        oui_to_role = self._device_hints.get("oui_to_role", {})
        if oui and isinstance(oui_to_role, dict):
            role = oui_to_role.get(oui.lower())
            if isinstance(role, str) and role.strip():
                return role.strip()

        # 2) vendor based (substring match)
        vendor_to_role = self._device_hints.get("vendor_to_role", {})
        if vendor and isinstance(vendor_to_role, dict):
            for vendor_key, role in vendor_to_role.items():
                if isinstance(vendor_key, str) and vendor_key.lower() in vendor.lower():
                    if isinstance(role, str) and role.strip():
                        return role.strip()

        # 3) hostname keyword based
        hostname_keywords = self._device_hints.get("hostname_keywords_to_role", {})
        if hostname and isinstance(hostname_keywords, dict):
            hn = hostname.lower()
            for keyword, role in hostname_keywords.items():
                if isinstance(keyword, str) and keyword.lower() in hn:
                    if isinstance(role, str) and role.strip():
                        return role.strip()

        return None