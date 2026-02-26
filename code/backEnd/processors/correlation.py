code/backEnd/processors/correlation.py

Purpose: Decide whether incoming events represent new vs existing hosts/edges, and produce entity updates + “signals” for main. Uses Librarian for read-only DB checks (Option B).
Inputs:

Enriched Events

Librarian read-only methods:

find_host_by_mac(mac)

find_host_by_ip(ip)

find_edge_by_hosts(a, b, proto/ports) (as needed)
Outputs:

Entity updates (to be upserted):

HostEntity updates

EdgeEntity updates (from traffic/flows)

Signals for main (control-plane info), e.g.:

new_host_detected: bool

targeted_scan_ip: str | None

new_edge_detected: bool

(optional) new_subnet_detected: bool

Does NOT:

trigger active discovery directly

write to Mongo directly