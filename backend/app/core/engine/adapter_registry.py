"""Engine — adapter registry: maps AdapterType to a live adapter instance."""
from __future__ import annotations

from ...adapters.api_adapter import ApiAdapter
from ...adapters.base import ExecutionAdapter
from ...adapters.browser_adapter import BrowserAdapter
from ...adapters.bu_browser_adapter import BrowserUseAdapter
from ...adapters.human_adapter import HumanAdapter
from ...adapters.internal_route_adapter import InternalRouteAdapter
from ...adapters.vision_adapter import VisionAdapter
from ...core.domain.enums import AdapterType


class AdapterRegistry:
    """Holds one instance per AdapterType; orchestrator looks up by enum."""

    def __init__(self) -> None:
        self._by_type: dict[AdapterType, ExecutionAdapter] = {}

    def register(self, adapter: ExecutionAdapter) -> None:
        """Register an adapter under its adapter_type."""
        self._by_type[adapter.adapter_type] = adapter

    def get(self, adapter_type: AdapterType) -> ExecutionAdapter:
        """Look up an adapter; raises KeyError if none registered."""
        if adapter_type not in self._by_type:
            raise KeyError(f"no adapter registered for {adapter_type}")
        return self._by_type[adapter_type]

    def all(self) -> dict[AdapterType, ExecutionAdapter]:
        """Return the full registry for inspection / diagnostics."""
        return dict(self._by_type)


def default_registry() -> AdapterRegistry:
    """Build a registry pre-populated with all six built-in adapters.

    The Browser Use adapter (``bu_browser``) is included here so it can be
    reached via the fallback chain when an action explicitly lists it in
    ``executionMethods`` — but it is NEVER the default path (the
    orchestrator's empty-chain default still places it after ``browser``
    and before ``vision``).
    """
    reg = AdapterRegistry()
    reg.register(ApiAdapter())
    reg.register(InternalRouteAdapter())
    reg.register(BrowserAdapter())
    reg.register(BrowserUseAdapter())
    reg.register(VisionAdapter())
    reg.register(HumanAdapter())
    return reg
