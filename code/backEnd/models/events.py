Purpose: Canonical in-memory “observations” passed through the pipeline (NOT stored by default).
Inputs: Created by sensors/extractors.
Outputs: Event objects such as:

HostSeen(ip, mac, ts, source, iface, confidence)

PortSeen(ip, port, proto, state, ts, source)

TrafficSeen(src_ip, dst_ip, proto, src_port, dst_port, bytes, ts, source)

Optional: FlowSummarySeen(...) if you summarize packets into flows.