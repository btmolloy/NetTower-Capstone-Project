code/backEnd/sensors/passive_listener.py

Purpose: Start tcpdump capture on a chosen interface and emit packet-derived events. Focus is topology/activity, not payload reconstruction.
Inputs:

interface name from config (e.g., eth0)

EventBus handle to publish events

capture settings (filters, sampling, flow aggregation window)
Outputs:

Publishes Event objects:

HostSeen (from ARP/DHCP/mDNS clues, etc.)

TrafficSeen or FlowSummarySeen (aggregated view recommended)

Does NOT write to DB.

Does NOT trigger scans.

Important behavior expectation:

Capture packet metadata and aggregate into flow/edge stats quickly to avoid high volume.