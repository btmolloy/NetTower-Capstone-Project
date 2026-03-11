from __future__ import annotations

import time

from pymongo import MongoClient

from backEnd.runtime.config import RuntimeConfig
from backEnd.runtime.session_config import SessionConfig
from backEnd.runtime.supervisor import Supervisor


def main() -> None:
    runtime_cfg = RuntimeConfig().validate()

    session_cfg = SessionConfig(
        enable_passive_listener=True,
        enable_active_discovery=False,
        interface="en0",
        discovery_target_cidr=None,
        discovery_interval_seconds=120,
        targeted_scan_cooldown_seconds=300,
    ).validate()

    sup = Supervisor(runtime_cfg)

    client: MongoClient | None = None

    try:
        sup.start_session(session_cfg)

        print("Session started. Monitoring DB for 20 seconds...\n")

        client = MongoClient(runtime_cfg.mongo_uri)
        db = client[runtime_cfg.mongo_db_name]

        hosts = db["hosts"]
        edges = db["edges"]

        start = time.time()
        poll_interval_seconds = 5

        while time.time() - start < 20:
            elapsed = int(time.time() - start)

            print(f"\n===== DB SNAPSHOT @ {elapsed}s =====")

            print("\n------ HOSTS ------")
            host_docs = list(hosts.find())
            if host_docs:
                for doc in host_docs:
                    print(doc)
            else:
                print("(no hosts found)")

            print("\n------ EDGES ------")
            edge_docs = list(edges.find())
            if edge_docs:
                for doc in edge_docs:
                    print(doc)
            else:
                print("(no edges found)")

            remaining = 20 - (time.time() - start)
            if remaining <= 0:
                break

            time.sleep(min(poll_interval_seconds, remaining))

    finally:
        print("\nStopping session...")
        try:
            sup.stop_session()
        except Exception as exc:
            print(f"Error while stopping session: {exc}")

        if client is not None:
            try:
                client.close()
            except Exception:
                pass

        print("Done.")


if __name__ == "__main__":
    main()