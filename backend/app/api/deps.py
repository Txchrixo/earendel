"""API — shared FastAPI dependencies (singletons)."""
from __future__ import annotations

from functools import lru_cache

from ..core.engine.adapter_registry import default_registry
from ..core.engine.orchestrator import Orchestrator
from ..core.registry.action_registry import ActionRegistry
from ..infrastructure.llm_client import LLMClient
from ..infrastructure.telemetry import TraceCollector


@lru_cache
def get_adapter_registry():
    """Return the process-wide AdapterRegistry singleton."""
    return default_registry()


@lru_cache
def get_action_registry() -> ActionRegistry:
    """Return the process-wide ActionRegistry singleton."""
    return ActionRegistry()


@lru_cache
def get_orchestrator() -> Orchestrator:
    """Return the process-wide Orchestrator singleton."""
    return Orchestrator(
        registry=get_adapter_registry(),
        action_registry=get_action_registry(),
        telemetry=TraceCollector(),
    )


@lru_cache
def get_llm_client() -> LLMClient:
    """Return the process-wide LLMClient singleton (real z-ai CLI + fallback)."""
    return LLMClient()
