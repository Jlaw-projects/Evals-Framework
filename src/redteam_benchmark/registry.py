"""Lightweight registries for discoverable benchmark components."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from importlib.metadata import entry_points
from typing import Any

from redteam_benchmark.errors import PluginRegistrationError


@dataclass(frozen=True)
class SuiteInfo:
    name: str
    version: str
    description: str
    cases: int
    rubric_version: str


@dataclass(frozen=True)
class ComponentInfo:
    name: str
    kind: str
    source: str = "built-in"
    target: str | None = None


_ADAPTERS: dict[str, Any] = {
    "mock": None,
    "ollama": None,
    "minimax": None,
    "openai-compatible": None,
}
_JUDGES: dict[str, Any] = {"rule-based": None, "openai-compatible-judge": None}
_MUTATORS: dict[str, Any] = {"safe_reframe": None}


def register_adapter(name: str, factory: Any) -> None:
    _register(_ADAPTERS, name, factory, "adapter")


def register_judge(name: str, factory: Any) -> None:
    _register(_JUDGES, name, factory, "judge")


def register_mutator(name: str, factory: Any) -> None:
    _register(_MUTATORS, name, factory, "mutator")


def _register(registry: dict[str, Any], name: str, factory: Any, kind: str) -> None:
    normalized = name.strip()
    if not normalized:
        raise PluginRegistrationError(f"Cannot register unnamed {kind}.")
    if normalized in registry:
        raise PluginRegistrationError(f"{kind.title()} already registered: {normalized}")
    registry[normalized] = factory


def list_suites() -> list[SuiteInfo]:
    suite_dir = resources.files("redteam_benchmark.datasets.suites")
    suites = []
    for item in suite_dir.iterdir():
        if item.name.endswith(".json"):
            payload = json.loads(item.read_text(encoding="utf-8"))
            suites.append(
                SuiteInfo(
                    name=payload["name"],
                    version=payload["version"],
                    description=payload.get("description", ""),
                    cases=len(payload.get("cases", [])),
                    rubric_version=payload.get("rubric_version", "rubric.v1"),
                )
            )
    return sorted(suites, key=lambda suite: (suite.name, suite.version))


def list_adapters() -> list[str]:
    return sorted(set(_ADAPTERS) | _entry_point_names("redteam_benchmark.adapters"))


def list_judges() -> list[str]:
    return sorted(set(_JUDGES) | _entry_point_names("redteam_benchmark.judges"))


def list_mutators() -> list[str]:
    return sorted(set(_MUTATORS) | _entry_point_names("redteam_benchmark.mutators"))


def list_components() -> list[ComponentInfo]:
    components = []
    for kind, names in {
        "adapter": list_adapters(),
        "judge": list_judges(),
        "mutator": list_mutators(),
    }.items():
        for name in names:
            source = (
                "entry-point"
                if name in _entry_point_names(f"redteam_benchmark.{kind}s")
                else "built-in"
            )
            components.append(ComponentInfo(name=name, kind=kind, source=source))
    return sorted(components, key=lambda item: (item.kind, item.name))


def resolve_adapter(name: str) -> Any:
    """Resolve a registered or entry-point adapter factory."""

    return _resolve(_ADAPTERS, "redteam_benchmark.adapters", name, "adapter")


def resolve_judge(name: str) -> Any:
    """Resolve a registered or entry-point judge factory."""

    return _resolve(_JUDGES, "redteam_benchmark.judges", name, "judge")


def resolve_mutator(name: str) -> Any:
    """Resolve a registered or entry-point mutator factory."""

    return _resolve(_MUTATORS, "redteam_benchmark.mutators", name, "mutator")


def _resolve(registry: dict[str, Any], group: str, name: str, kind: str) -> Any:
    normalized = name.strip()
    if normalized in registry and registry[normalized] is not None:
        return registry[normalized]
    for item in _entry_points(group):
        if item.name == normalized:
            return item.load()
    if normalized in registry:
        raise PluginRegistrationError(
            f"Built-in {kind} '{normalized}' is selected internally and has no plugin factory."
        )
    raise PluginRegistrationError(f"Unknown {kind}: {normalized}")


def _entry_point_names(group: str) -> set[str]:
    return {item.name for item in _entry_points(group)}


def _entry_points(group: str) -> list[Any]:
    try:
        discovered = entry_points(group=group)
    except TypeError:  # pragma: no cover - compatibility with older importlib.metadata
        legacy_entry_points: Any = entry_points()
        discovered = legacy_entry_points.get(group, [])
    return list(discovered)
