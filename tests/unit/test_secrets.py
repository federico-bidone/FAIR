import types

import pytest
import pytest

from fair3.engine.infra import secrets


@pytest.fixture
def dummy_keyring(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict[str, str]]:
    storage: dict[str, dict[str, str]] = {}

    class _Errors:
        class PasswordDeleteError(Exception):
            pass

        class KeyringError(Exception):
            pass

    class DummyKeyring:
        errors = _Errors

        def set_password(self, service: str, username: str, password: str) -> None:
            storage.setdefault(service, {})[username] = password

        def get_password(self, service: str, username: str) -> str | None:
            return storage.get(service, {}).get(username)

        def delete_password(self, service: str, username: str) -> None:
            try:
                del storage[service][username]
            except KeyError as exc:  # pragma: no cover - defensive branch
                raise self.errors.PasswordDeleteError from exc

    monkeypatch.setattr(secrets, "keyring", DummyKeyring())
    return storage


def test_set_and_get_secret(dummy_keyring: dict[str, dict[str, str]]) -> None:
    secrets.set_secret("alphavantage_api_key", "default", "alpha123")
    assert secrets.get_secret("alphavantage_api_key", "default") == "alpha123"


def test_delete_secret(dummy_keyring: dict[str, dict[str, str]]) -> None:
    secrets.set_secret("fred_api_key", "default", "fred")
    secrets.set_secret("fred_api_key", "default", None)
    assert secrets.get_secret("fred_api_key", "default") is None


def test_missing_backend_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(secrets, "keyring", None)
    with pytest.raises(RuntimeError):
        secrets.set_secret("tiingo_api_key", "default", "token")
    assert secrets.get_secret("tiingo_api_key", "default") is None
