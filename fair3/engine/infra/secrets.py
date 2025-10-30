"""Keyring-backed helpers for persisting FAIR API credentials."""

from __future__ import annotations

import logging
from typing import Final

try:  # pragma: no cover - optional dependency
    import keyring  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - optional dependency
    keyring = None  # type: ignore[assignment]

LOG = logging.getLogger(__name__)
_SERVICE_PREFIX: Final[str] = "fair3"


def _qualify(service: str) -> str:
    return f"{_SERVICE_PREFIX}:{service}".lower()


def is_backend_available() -> bool:
    """Return ``True`` when the keyring backend can be used."""

    return keyring is not None


def set_secret(service: str, username: str, value: str | None) -> None:
    """Persist ``value`` inside the configured keyring backend."""

    if keyring is None:  # pragma: no cover - guard against optional dependency
        raise RuntimeError("keyring is not installed; install the gui extras to enable secrets")
    qualified = _qualify(service)
    if value:
        keyring.set_password(qualified, username, value)
        LOG.debug("Stored credential for service=%s user=%s", qualified, username)
    else:
        try:
            keyring.delete_password(qualified, username)
        except keyring.errors.PasswordDeleteError:  # type: ignore[attr-defined]
            LOG.debug("No existing credential to delete for %s/%s", qualified, username)


def get_secret(service: str, username: str) -> str | None:
    """Retrieve a previously stored credential from the keyring."""

    if keyring is None:  # pragma: no cover - optional dependency
        return None
    qualified = _qualify(service)
    try:
        return keyring.get_password(qualified, username)
    except keyring.errors.KeyringError:  # type: ignore[attr-defined]
        LOG.warning("Keyring backend raised an error for %s/%s", qualified, username)
        return None


__all__ = ["get_secret", "is_backend_available", "set_secret"]
