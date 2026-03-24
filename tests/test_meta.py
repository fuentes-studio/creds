"""Tests for SQLite metadata store."""
import pytest
from creds.meta import MetaStore


@pytest.fixture
def store(tmp_path):
    return MetaStore(db_path=tmp_path / "meta.db")


def test_upsert_and_get(store):
    store.upsert("anthropic", "", "api_key", context="personal")
    meta = store.get("anthropic", "", "api_key")
    assert meta is not None
    assert meta.service_id == "anthropic"
    assert meta.context == "personal"
    assert meta.status == "active"


def test_upsert_idempotent(store):
    store.upsert("anthropic", "", "api_key")
    store.upsert("anthropic", "", "api_key")
    meta = store.get("anthropic", "", "api_key")
    assert meta is not None


def test_delete(store):
    store.upsert("anthropic", "", "api_key")
    store.delete("anthropic", "", "api_key")
    assert store.get("anthropic", "", "api_key") is None


def test_flag_and_unflag(store):
    store.upsert("anthropic", "", "api_key")
    store.flag("anthropic", "", "api_key", reason="401 from API")
    meta = store.get("anthropic", "", "api_key")
    assert meta.status == "flagged"
    assert meta.flag_reason == "401 from API"
    assert meta.flagged_at is not None

    store.unflag("anthropic", "", "api_key")
    meta = store.get("anthropic", "", "api_key")
    assert meta.status == "active"
    assert meta.flag_reason is None


def test_instance_credential(store):
    store.upsert("slack", "Acme", "bot_token", context="work")
    meta = store.get("slack", "Acme", "bot_token")
    assert meta.instance == "Acme"
    assert meta.context == "work"


def test_all_for_service(store):
    store.upsert("google-oauth", "my-project", "client_id")
    store.upsert("google-oauth", "my-project", "client_secret")
    store.upsert("google-oauth", "personal", "client_id")
    metas = store.all_for_service("google-oauth")
    assert len(metas) == 3


def test_settings_defaults(store):
    assert store.setting("rotation_warn_days") == "90"
    assert store.setting("rotation_overdue_days") == "180"


def test_set_setting(store):
    store.set_setting("rotation_warn_days", "60")
    assert store.setting("rotation_warn_days") == "60"
