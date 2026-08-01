"""Typed errors for agent-fury."""

from __future__ import annotations


class FuryError(Exception):
    """Base class for all agent-fury errors."""


class ConfigError(FuryError):
    """Something is wrong with configuration (missing key, bad model spec, …)."""


class ProviderError(FuryError):
    """A provider adapter failed to talk to its backend."""


class ProviderNotAvailable(ConfigError):
    """A provider was requested but its SDK/key/endpoint isn't available."""
