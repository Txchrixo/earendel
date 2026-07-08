"""Shared kernel — domain errors."""
from __future__ import annotations


class EarendelError(Exception):
    """Base error for the Earendel domain."""


class NotFoundError(EarendelError):
    def __init__(self, entity: str, entity_id: str):
        super().__init__(f"{entity} '{entity_id}' not found")
        self.entity = entity
        self.entity_id = entity_id


class ValidationError(EarendelError):
    def __init__(self, message: str):
        super().__init__(message)


class ExecutionError(EarendelError):
    def __init__(self, message: str, *, adapter: str | None = None):
        super().__init__(message)
        self.adapter = adapter
