"""Typed error hierarchy for benchmark execution and validation."""

from __future__ import annotations


class BenchmarkError(Exception):
    """Base class for expected benchmark-domain failures."""


class AdapterError(BenchmarkError):
    """Target or judge model transport failed or returned malformed data."""


class SuiteValidationError(BenchmarkError):
    """A benchmark suite failed schema, safety, or reproducibility validation."""


class PluginRegistrationError(BenchmarkError):
    """A plugin registration conflicts with an existing benchmark component."""


class SelfImprovementError(BenchmarkError):
    """The self-improvement loop could not produce a safe auditable result."""
