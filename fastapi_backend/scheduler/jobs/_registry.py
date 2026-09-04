from __future__ import annotations

import importlib
import pkgutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JobSpec:
    key: str
    title: str
    runner: Callable[..., dict[str, Any]]
    concurrency_key: str | None = None
    description: str | None = None


_REGISTRY: dict[str, JobSpec] = {}
_discovered = False

# Non-job modules under scheduler.jobs that must not be auto-imported as runners.
_SKIP_MODULE_SUFFIXES = frozenset({"registry"})


def job(
    key: str,
    *,
    title: str,
    concurrency_key: str | None = None,
    description: str | None = None,
):
    """Register a job runner discovered via ``discover()``."""

    def deco(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        if key in _REGISTRY:
            raise RuntimeError(
                f"duplicate job_key {key!r}: "
                f"{_REGISTRY[key].runner.__module__} vs {fn.__module__}"
            )
        _REGISTRY[key] = JobSpec(key, title, fn, concurrency_key, description)
        return fn

    return deco


def _should_skip_module(fullname: str) -> bool:
    parts = fullname.split(".")
    if any(p.startswith("_") for p in parts):
        return True
    if parts and parts[-1] in _SKIP_MODULE_SUFFIXES:
        return True
    return False


def discover(package: str = "scheduler.jobs") -> dict[str, JobSpec]:
    """Walk the package and register every ``@job``-decorated runner."""
    global _discovered
    if _discovered:
        return _REGISTRY
    pkg = importlib.import_module(package)
    for m in pkgutil.walk_packages(pkg.__path__, prefix=f"{package}."):
        if _should_skip_module(m.name):
            continue
        importlib.import_module(m.name)
    _discovered = True
    return _REGISTRY


def get_registry() -> dict[str, JobSpec]:
    return discover()


def reset_discovery_for_tests() -> None:
    """Clear discovery state and drop cached job modules — tests only."""
    global _discovered
    _REGISTRY.clear()
    _discovered = False
    prefix = "scheduler.jobs."
    for name in list(sys.modules):
        if not name.startswith(prefix):
            continue
        if _should_skip_module(name):
            continue
        del sys.modules[name]
