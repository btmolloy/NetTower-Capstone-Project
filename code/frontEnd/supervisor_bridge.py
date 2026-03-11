#!/usr/bin/env python3
"""
JSON-line bridge between Electron and NetTower Supervisor.

Commands accepted on stdin:
- start_session
- stop_session
- status
- shutdown

Each request must be JSON:
{"id": 1, "command": "start_session", "payload": {...}}
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any

# Ensure imports work when this script is launched from frontEnd/.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backEnd.runtime.config import RuntimeConfig
from backEnd.runtime.session_config import SessionConfig
from backEnd.runtime.supervisor import Supervisor


def send_json(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def response_ok(command_id: int, result: dict[str, Any] | None = None) -> None:
    send_json(
        {
            "id": command_id,
            "ok": True,
            "result": result or {},
        }
    )


def response_error(command_id: int | None, message: str) -> None:
    payload: dict[str, Any] = {
        "ok": False,
        "error": message,
    }
    if command_id is not None:
        payload["id"] = command_id
    send_json(payload)


def serialize_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [serialize_value(v) for v in value]
    return str(value)


def get_topology_snapshot(runtime_cfg: RuntimeConfig, limit_hosts: int, limit_edges: int) -> dict[str, Any]:
    captured_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        from pymongo import MongoClient  # type: ignore
    except Exception as exc:
        return {
            "hosts": [],
            "edges": [],
            "warning": f"pymongo unavailable: {exc}",
            "captured_at": captured_at,
        }

    client = None
    try:
        client = MongoClient(runtime_cfg.mongo_uri, serverSelectionTimeoutMS=800)
        db = client[runtime_cfg.mongo_db_name]

        host_projection = {
            "_id": 0,
            "host_id": 1,
            "ips": 1,
            "macs": 1,
            "vendor": 1,
            "os_guess": 1,
            "first_seen": 1,
            "last_seen": 1,
            "ports": 1,
        }
        edge_projection = {
            "_id": 0,
            "edge_key": 1,
            "a_host_id": 1,
            "b_host_id": 1,
            "proto": 1,
            "first_seen": 1,
            "last_seen": 1,
            "count": 1,
            "ports": 1,
        }

        hosts = list(
            db["hosts"]
            .find({}, host_projection)
            .sort("last_seen", -1)
            .limit(limit_hosts)
        )
        edges = list(
            db["edges"]
            .find({}, edge_projection)
            .sort("last_seen", -1)
            .limit(limit_edges)
        )

        return {
            "hosts": serialize_value(hosts),
            "edges": serialize_value(edges),
            "captured_at": captured_at,
        }
    except Exception as exc:
        return {
            "hosts": [],
            "edges": [],
            "warning": f"topology snapshot unavailable: {exc}",
            "captured_at": captured_at,
        }
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def handle_command(
    supervisor: Supervisor,
    runtime_cfg: RuntimeConfig,
    command: str,
    payload: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    if command == "start_session":
        session_payload = payload.get("session_config") or {}
        session_cfg = SessionConfig.from_dict(session_payload).validate()
        supervisor.start_session(session_cfg)
        return True, {"running": supervisor.is_running()}

    if command == "stop_session":
        supervisor.stop_session()
        return True, {"running": supervisor.is_running()}

    if command == "status":
        return True, {"running": supervisor.is_running()}

    if command == "get_topology_snapshot":
        limit_hosts = int(payload.get("limit_hosts", 250))
        limit_edges = int(payload.get("limit_edges", 500))
        limit_hosts = max(10, min(2000, limit_hosts))
        limit_edges = max(10, min(4000, limit_edges))
        snapshot = get_topology_snapshot(runtime_cfg, limit_hosts, limit_edges)
        snapshot["running"] = supervisor.is_running()
        return True, snapshot

    if command == "shutdown":
        if supervisor.is_running():
            supervisor.stop_session()
        return False, {"running": False}

    raise ValueError(f"Unknown command: {command}")


def main() -> int:
    runtime_cfg = RuntimeConfig(launch_frontend=False).validate()
    supervisor = Supervisor(runtime_cfg)

    keep_running = True
    try:
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue

            command_id: int | None = None
            try:
                request = json.loads(line)
                command_id = int(request["id"])
                command = str(request["command"])
                payload = request.get("payload") or {}

                keep_running, result = handle_command(supervisor, runtime_cfg, command, payload)
                response_ok(command_id, result)

                if not keep_running:
                    break
            except Exception as exc:
                response_error(command_id, f"{exc.__class__.__name__}: {exc}")

    except KeyboardInterrupt:
        pass
    finally:
        if supervisor.is_running():
            try:
                supervisor.stop_session()
            except Exception:
                pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
