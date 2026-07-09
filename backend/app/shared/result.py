"""Shared kernel — Result type for explicit error handling (no exceptions in domain layer)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Result(Generic[T]):
    """Discriminated union: either Ok(value) or Err(message).

    Domain services return Result rather than raising, so callers must handle
    the failure case explicitly (SOLID — no hidden control flow)."""

    ok: bool
    value: T | None
    error: str | None

    @staticmethod
    def ok_(value: T) -> "Result[T]":
        return Result(ok=True, value=value, error=None)

    @staticmethod
    def err(message: str) -> "Result[T]":
        return Result(ok=False, value=None, error=message)

    def unwrap(self) -> T:
        if not self.ok or self.value is None:
            raise RuntimeError(f"Result unwrap on error: {self.error}")
        return self.value
