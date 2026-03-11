"""
Runtime bootstrap layer for NetTower.

This package owns:
- startup settings / launch overrides
- runtime path resolution
- bundled binary resolution
- embedded service lifecycle
- supervisor orchestration
- shutdown sequencing

It does NOT own backend event processing, sensors, or correlation logic.
"""