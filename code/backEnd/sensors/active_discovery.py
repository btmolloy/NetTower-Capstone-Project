code/backEnd/sensors/active_discovery.py

Purpose: Run active scanning jobs (interval and targeted) using nmap/ping/arp and emit Events describing findings.
Inputs:

target(s): subnet CIDR or single IP (targeted scan)

config scan options (timeout, port sets, etc.)

EventBus to publish results
Outputs:

Publishes Events such as:

HostSeen (host exists/reachable)

PortSeen (open/closed)

ServiceSeen (if you choose)

OsGuessSeen (optional event or part of enriched entity)

Owned by: Called/scheduled by main.py.