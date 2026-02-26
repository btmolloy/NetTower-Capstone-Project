Purpose: Orchestrator. Boots the app, starts passive listener, schedules interval scans, runs the pipeline, writes to Mongo, and triggers targeted scans when new hosts appear.
Inputs:

Config from config.py

Events from EventBus

Correlation results (updates + signals)

User-triggered scan requests (later via API/UI)
Outputs:

Starts background sensor processes/threads

Calls active_discovery on interval and targeted triggers

Persists entities/edges via Librarian

Publishes any generated events back into the EventBus

Key behaviors owned by main:

Passive listener starts immediately at launch.

Active discovery runs:

on interval (config.discovery_interval_seconds)

and on targeted trigger when correlation reports new_host_detected

Anti-spam for targeted scans (cooldown per IP).