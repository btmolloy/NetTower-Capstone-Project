code/backEnd/processors/enrichment.py

Purpose: Add meaning to canonical events: vendor lookup (OUI), OS hints, role hints, normalize MAC/IP formats.
Inputs:

Canonical Events

Reference data from resources/oui_vendors.json and resources/device_hints.json
Outputs:

Enriched Events (same event with extra fields or a new enriched event type)

Does NOT write DB.