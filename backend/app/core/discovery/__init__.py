"""Network discovery (Option B) — HAR analysis + endpoint store.

Turns raw HAR captures from the recording phase into scored, clustered,
DB-backed ``DiscoveredEndpoint`` rows that the ``internal_route`` adapter
replays at runtime instead of clicking through the browser.

Public surface:
  - :class:`DiscoveredEndpointCandidate`  (har_analyzer)
  - :func:`analyze_har`                   (har_analyzer)
  - :func:`store_discovered_endpoints`    (endpoint_store)
  - :func:`get_best_endpoint`             (endpoint_store)
  - :func:`mark_stale`                    (endpoint_store)
  - :func:`record_replay`                 (endpoint_store)
  - :func:`list_endpoints`                (endpoint_store)
"""
from __future__ import annotations
