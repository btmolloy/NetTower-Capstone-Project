from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any


@dataclass(frozen=True)
class mongo_handles:
    client: Any
    db: Any
    hosts: Any
    edges: Any


class mongo_client_manager:
    """
    Central MongoDB connection + collection handles + index setup.

    Owned by main.py (created once, closed on shutdown).
    Used by librarian.py to perform reads/writes.
    """

    def __init__(self, cfg: Any) -> None:
        self._cfg = cfg
        self._handles: Optional[mongo_handles] = None

    def connect(self) -> mongo_handles:
        """
        Connect to Mongo and ensure indexes exist.
        Safe to call multiple times; returns cached handles.
        """

        if self._handles is not None:
            return self._handles

        try:
            from pymongo import MongoClient  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "pymongo is required for MongoDB storage. Install with: pip install pymongo"
            ) from exc

        # ---------------------------------------------------------
        # Resolve Mongo connection settings
        # ---------------------------------------------------------

        mongo_uri = getattr(self._cfg, "mongo_uri", "mongodb://127.0.0.1:27017")
        mongo_db_name = getattr(self._cfg, "mongo_db_name", "nettower")

        client = MongoClient(mongo_uri)
        db = client[mongo_db_name]

        hosts = db["hosts"]
        edges = db["edges"]

        # ---------------------------------------------------------
        # Index setup
        # ---------------------------------------------------------

        # Hosts
        hosts.create_index("host_id", unique=True)
        hosts.create_index("macs")
        hosts.create_index("ips")
        hosts.create_index("last_seen")

        # Edges
        edges.create_index("edge_key", unique=True)
        edges.create_index([("a_host_id", 1), ("b_host_id", 1), ("proto", 1)])
        edges.create_index("last_seen")

        self._handles = mongo_handles(
            client=client,
            db=db,
            hosts=hosts,
            edges=edges,
        )

        return self._handles

    def handles(self) -> mongo_handles:
        """
        Return handles (connect if needed).
        """
        return self.connect()

    def close(self) -> None:
        """
        Close Mongo client if open.
        """

        if self._handles is None:
            return

        try:
            self._handles.client.close()
        finally:
            self._handles = None