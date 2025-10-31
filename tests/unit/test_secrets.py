import types

import os

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


def test_save_and_load_secret(dummy_keyring: dict[str, dict[str, str]]) -> None:
    stored = secrets.save_api_keys({"ALPHAVANTAGE_API_KEY": "alpha123"})
    assert stored["ALPHAVANTAGE_API_KEY"] == "alpha123"
    loaded = secrets.load_api_keys()
    assert loaded == stored
    assert secrets.get_api_key("ALPHAVANTAGE_API_KEY") == "alpha123"


def test_delete_secret(dummy_keyring: dict[str, dict[str, str]]) -> None:
    secrets.save_api_keys({"FRED_API_KEY": "fred"})
    secrets.save_api_keys({"FRED_API_KEY": None})
    assert "FRED_API_KEY" not in secrets.load_api_keys()
    assert secrets.get_api_key("FRED_API_KEY") is None


def test_apply_api_keys_sets_environment(
    dummy_keyring: dict[str, dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TIINGO_API_KEY", raising=False)
    secrets.save_api_keys({"TIINGO_API_KEY": "token123"})
    secrets.apply_api_keys(secrets.load_api_keys())
    assert os.environ["TIINGO_API_KEY"] == "token123"


def test_missing_backend_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(secrets, "keyring", None)
    with pytest.raises(RuntimeError):
        secrets.save_api_keys({"TIINGO_API_KEY": "token"})
    assert secrets.get_api_key("TIINGO_API_KEY") is None
