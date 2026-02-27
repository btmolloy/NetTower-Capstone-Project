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

        client = MongoClient(self._cfg.mongo_uri)
        db = client[self._cfg.mongo_db_name]

        hosts = db["hosts"]
        edges = db["edges"]

        # ---- Indexes (minimal but critical) ----
        # Hosts:
        #   - host_id unique (stable primary key)
        #   - macs and ips for correlation lookups
        hosts.create_index("host_id", unique=True)
        hosts.create_index("macs")
        hosts.create_index("ips")
        hosts.create_index("last_seen")

        # Edges:
        #   - edge_key unique (stable pair+proto key)
        #   - host ids for querying adjacency
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