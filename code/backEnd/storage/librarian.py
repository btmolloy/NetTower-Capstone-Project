code/backEnd/storage/librarian.py

Purpose: Storage gateway. Performs Mongo upserts for entities and provides read-only lookup functions for correlation.
Inputs:

HostEntity, EdgeEntity (from correlation)

Lookup queries from correlation (mac/ip/edge)
Outputs:

MongoDB documents inserted/updated

Lookup results returned to correlation (None if not found)

Key read-only functions expected:

find_host_by_mac(mac) -> HostEntity|None

find_host_by_ip(ip) -> HostEntity|None

find_edge(...) -> EdgeEntity|None

Key write functions expected:

upsert_host(host_entity)

upsert_edge(edge_entity)