"""Keyring-backed helpers for FAIR API credentials."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping

try:  # pragma: no cover - optional dependency
    import keyring  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    keyring = None  # type: ignore[assignment]

LOG = logging.getLogger(__name__)
_SERVICE_PREFIX = "fair3"
_USERNAME = "default"
_REGISTRY_USER = "__registry__"
_REGISTRY_SERVICE = f"{_SERVICE_PREFIX}:registry"


def _qualify(env: str) -> str:
    return f"{_SERVICE_PREFIX}:{env}".lower()


def _ensure_backend() -> object:
    if keyring is None:  # pragma: no cover - optional dependency guard
        raise RuntimeError("keyring is not installed; install the gui extras to enable secrets")
    return keyring


def _load_registry() -> set[str]:
    if keyring is None:  # pragma: no cover - optional dependency guard
        return set()
    try:
        payload = keyring.get_password(_REGISTRY_SERVICE, _REGISTRY_USER)
    except keyring.errors.KeyringError:  # type: ignore[attr-defined]
        LOG.warning("Unable to read FAIR key registry from keyring backend")
        return set()
    if not payload:
        return set()
    try:
        entries = json.loads(payload)
    except json.JSONDecodeError:  # pragma: no cover - defensive guard
        LOG.warning("Invalid FAIR key registry payload; resetting")
        return set()
    return {str(item).upper() for item in entries}


def _store_registry(entries: set[str]) -> None:
    backend = _ensure_backend()
    if entries:
        backend.set_password(
            _REGISTRY_SERVICE,
            _REGISTRY_USER,
            json.dumps(sorted(entries)),
        )
    else:
        try:
            backend.delete_password(_REGISTRY_SERVICE, _REGISTRY_USER)
        except backend.errors.PasswordDeleteError:  # type: ignore[attr-defined]
            LOG.debug("Registry already empty when deleting")


def is_backend_available() -> bool:
    """Return ``True`` when the keyring backend can be used."""

    return keyring is not None


def save_api_keys(mapping: Mapping[str, str | None]) -> dict[str, str]:
    """Persist API keys and return the full stored mapping."""

    backend = _ensure_backend()
    registry = _load_registry()
    updates: dict[str, str] = {}
    removals: set[str] = set()
    for raw_env, raw_value in mapping.items():
        env = raw_env.strip().upper()
        if not env:
            continue
        value = (raw_value or "").strip()
        qualified = _qualify(env)
        if value:
            backend.set_password(qualified, _USERNAME, value)
            registry.add(env)
            updates[env] = value
            LOG.debug("Stored credential for %s", env)
        else:
            try:
                backend.delete_password(qualified, _USERNAME)
            except backend.errors.PasswordDeleteError:  # type: ignore[attr-defined]
                LOG.debug("No credential to delete for %s", env)
            registry.discard(env)
            removals.add(env)
    _store_registry(registry)
    stored = load_api_keys()
    stored.update(updates)
    for env in removals:
        stored.pop(env, None)
    return stored


def load_api_keys() -> dict[str, str]:
    """Load every stored API key from the keyring registry."""

    if keyring is None:  # pragma: no cover - optional dependency guard
        return {}
    values: dict[str, str] = {}
    for env in _load_registry():
        qualified = _qualify(env)
        try:
            value = keyring.get_password(qualified, _USERNAME)
        except keyring.errors.KeyringError:  # type: ignore[attr-defined]
            LOG.warning("Keyring backend raised an error while reading %s", env)
            continue
        if value:
            values[env] = value
    return values


def get_api_key(env: str) -> str | None:
    """Convenience accessor returning the key for ``env`` if present."""

    env = env.strip().upper()
    return load_api_keys().get(env)


def apply_api_keys(mapping: Mapping[str, str | None]) -> None:
    """Mirror stored secrets into the current process environment."""

    for env, value in mapping.items():
        if value:
            os.environ[env] = value


__all__ = [
    "apply_api_keys",
    "get_api_key",
    "is_backend_available",
    "load_api_keys",
    "save_api_keys",
]
