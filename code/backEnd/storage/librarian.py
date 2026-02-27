from __future__ import annotations

from typing import Optional, Any

from backEnd.models.entities import host_entity, edge_entity


class librarian:
    """
    Storage gateway for MongoDB.

    - Correlation uses only read methods here (find_*).
    - main uses write methods here (upsert_*).
    """

    def __init__(self, mongo: Any) -> None:
        """
        mongo can be:
          - mongo_client_manager (recommended), or
          - mongo_handles (if you pass handles directly)
        """
        # Support both manager and handles objects
        handles = mongo.handles() if hasattr(mongo, "handles") else mongo

        self._hosts = handles.hosts
        self._edges = handles.edges

    # --------------------
    # Read-only lookups
    # --------------------

    def find_host_by_mac(self, mac: str) -> Optional[host_entity]:
        doc = self._hosts.find_one({"macs": mac})
        if not doc:
            return None
        return host_entity.from_dict(doc)

    def find_host_by_ip(self, ip: str) -> Optional[host_entity]:
        doc = self._hosts.find_one({"ips": ip})
        if not doc:
            return None
        return host_entity.from_dict(doc)

    def find_host_by_id(self, host_id: str) -> Optional[host_entity]:
        doc = self._hosts.find_one({"host_id": host_id})
        if not doc:
            return None
        return host_entity.from_dict(doc)

    def find_edge_by_key(self, edge_key: str) -> Optional[edge_entity]:
        doc = self._edges.find_one({"edge_key": edge_key})
        if not doc:
            return None
        return edge_entity.from_dict(doc)

    def find_edge(self, a_host_id: str, b_host_id: str, proto: str) -> Optional[edge_entity]:
        key = edge_entity.make_edge_key(a_host_id, b_host_id, proto)
        return self.find_edge_by_key(key)

    # --------------------
    # Writes / upserts
    # --------------------

    def upsert_host(self, entity: host_entity) -> None:
        doc = entity.to_dict()

        # first_seen should only be set once on insert
        first_seen = doc.get("first_seen")
        last_seen = doc.get("last_seen")

        update_doc = {
            "$set": {
                "ips": doc.get("ips", []),
                "macs": doc.get("macs", []),
                "vendor": doc.get("vendor"),
                "os_guess": doc.get("os_guess"),
                "last_seen": last_seen,
                "ports": doc.get("ports", []),
            },
            "$setOnInsert": {
                "host_id": doc["host_id"],
                "first_seen": first_seen,
            },
        }

        self._hosts.update_one({"host_id": doc["host_id"]}, update_doc, upsert=True)

    def upsert_edge(self, entity: edge_entity) -> None:
        doc = entity.to_dict()

        first_seen = doc.get("first_seen")
        last_seen = doc.get("last_seen")

        update_doc = {
            "$set": {
                "a_host_id": doc["a_host_id"],
                "b_host_id": doc["b_host_id"],
                "proto": doc["proto"],
                "last_seen": last_seen,
                "count": doc.get("count", 0),
                "ports": doc.get("ports", []),
            },
            "$setOnInsert": {
                "edge_key": doc["edge_key"],
                "first_seen": first_seen,
            },
        }

        self._edges.update_one({"edge_key": doc["edge_key"]}, update_doc, upsert=True)