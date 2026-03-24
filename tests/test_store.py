"""Tests for unified Store."""
import pytest
from unittest.mock import MagicMock
from creds.store import Store
from creds.keychain import KeychainItemNotFound


@pytest.fixture
def store(mocker):
    mocker.patch("creds.store.MetaStore.__init__", lambda self: None)
    mocker.patch("creds.store.Registry.__init__", lambda self, **kw: None)
    s = Store.__new__(Store)
    s.meta = MagicMock()
    s.registry = MagicMock()
    return s


def test_get_single_field_service(store, mocker):
    svc = MagicMock()
    svc.fields = [MagicMock(id="api_key")]
    store.registry.get.return_value = svc
    mocker.patch("creds.store.keychain.get", return_value="sk-ant-123")
    result = store.get("anthropic")
    assert result == "sk-ant-123"


def test_get_raises_when_missing(store, mocker):
    svc = MagicMock()
    svc.fields = [MagicMock(id="api_key")]
    store.registry.get.return_value = svc
    mocker.patch("creds.store.keychain.get", side_effect=KeychainItemNotFound)
    with pytest.raises(KeychainItemNotFound):
        store.get("anthropic")


def test_set_calls_keychain_and_meta(store, mocker):
    mock_kc_set = mocker.patch("creds.store.keychain.set")
    store.set("anthropic", "", "api_key", "sk-ant-123", context="personal")
    mock_kc_set.assert_called_once_with("anthropic.api_key", "sk-ant-123")
    store.meta.upsert.assert_called_once_with(
        "anthropic", "", "api_key", context="personal"
    )


def test_get_multi_field_requires_field_id(store):
    svc = MagicMock()
    svc.fields = [MagicMock(id="client_id"), MagicMock(id="client_secret")]
    store.registry.get.return_value = svc
    with pytest.raises(ValueError, match="multiple fields"):
        store.get("google-oauth")


def test_exists_true(store, mocker):
    svc = MagicMock()
    svc.fields = [MagicMock(id="api_key")]
    store.registry.get.return_value = svc
    mocker.patch("creds.store.keychain.exists", return_value=True)
    assert store.exists("anthropic") is True


def test_exists_false(store, mocker):
    svc = MagicMock()
    svc.fields = [MagicMock(id="api_key")]
    store.registry.get.return_value = svc
    mocker.patch("creds.store.keychain.exists", return_value=False)
    assert store.exists("anthropic") is False
