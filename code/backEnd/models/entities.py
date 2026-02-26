Purpose: Canonical “current state” objects meant to be stored in MongoDB and served to the UI.
Inputs: Produced by correlation (from events).
Outputs: Entities such as:

HostEntity (host_id, ips, macs, vendor, os_guess, ports, first_seen, last_seen)

EdgeEntity (a↔b relationship, counts, first_seen, last_seen, ports/protocols)

Optional: SubnetEntity (cidr, host_ids, last_seen)