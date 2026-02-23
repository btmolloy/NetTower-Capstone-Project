from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import ipaddress
import random

app = FastAPI(title="NetTower Backend")

# Allow the frontend (opened in a browser) to call the API easily during dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}

@app.get("/api/discover")
def discover(subnet: str = Query(..., description="CIDR subnet like 10.10.30.0/24")):
    """
    Baseline agentless discovery placeholder.
    For now: validates CIDR + returns a small simulated host list.
    Next sprint: replace 'simulate_hosts' with real scanning/parsing logic.
    """
    network = ipaddress.ip_network(subnet, strict=False)

    # Simulate 3–8 "up" hosts from the subnet for a working MVP
    hosts = simulate_hosts(network)

    return {
        "subnet": str(network),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "hosts": hosts,
        "count": len(hosts),
    }

def simulate_hosts(network: ipaddress._BaseNetwork):
    # Pick random hosts from the subnet (skipping network/broadcast automatically)
    all_hosts = list(network.hosts())
    if not all_hosts:
        return []

    sample_size = min(len(all_hosts), random.randint(3, 8))
    chosen = random.sample(all_hosts, sample_size)

    out = []
    for ip in sorted(chosen):
        out.append({
            "ip": str(ip),
            "status": "up",
            "hostname": None,
            "mac": None,
            "vendor": None,
        })
    return out