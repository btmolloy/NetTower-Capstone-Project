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

    def list_hosts(self, limit: int = 5000) -> list[host_entity]:
        cursor = self._hosts.find({}).sort("last_seen", -1).limit(max(1, int(limit)))
        return [host_entity.from_dict(doc) for doc in cursor]

    def list_edges(self, limit: int = 10000) -> list[edge_entity]:
        cursor = self._edges.find({}).sort("last_seen", -1).limit(max(1, int(limit)))
        return [edge_entity.from_dict(doc) for doc in cursor]

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
                "hostnames": doc.get("hostnames", []),
                "vendor": doc.get("vendor"),
                "os_guess": doc.get("os_guess"),
                "role": doc.get("role"),
                "role_confidence": doc.get("role_confidence"),
                "role_scores": doc.get("role_scores", {}),
                "node_role": doc.get("node_role"),
                "node_role_confidence": doc.get("node_role_confidence"),
                "parent_candidate": doc.get("parent_candidate"),
                "parent_confidence": doc.get("parent_confidence"),
                "topology_layer": doc.get("topology_layer"),
                "is_external": doc.get("is_external"),
                "last_seen": last_seen,
                "ports": doc.get("ports", []),
                "services": doc.get("services", []),
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
                "relation": doc.get("relation", "observed-traffic-peer"),
                "relationship_type": doc.get("relationship_type", doc.get("relation", "observed-traffic-peer")),
                "inferred": doc.get("inferred", False),
                "confidence": doc.get("confidence", 1.0),
                "evidence": doc.get("evidence", []),
            },
            "$setOnInsert": {
                "edge_key": doc["edge_key"],
                "first_seen": first_seen,
            },
        }

        self._edges.update_one({"edge_key": doc["edge_key"]}, update_doc, upsert=True)
