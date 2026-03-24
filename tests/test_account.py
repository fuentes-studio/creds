"""Tests for account key formatting."""
import pytest
from creds.account import account_key, parse_account_key


def test_single_field_service():
    assert account_key("anthropic", "", "api_key") == "anthropic.api_key"


def test_multi_instance_service():
    assert account_key("slack", "Acme", "bot_token") == "slack[Acme].bot_token"


def test_instance_with_spaces():
    assert account_key("slack", "My Workspace", "app_token") == "slack[My Workspace].app_token"


def test_parse_single():
    svc, inst, field = parse_account_key("anthropic.api_key")
    assert svc == "anthropic"
    assert inst == ""
    assert field == "api_key"


def test_parse_multi_instance():
    svc, inst, field = parse_account_key("slack[Acme].bot_token")
    assert svc == "slack"
    assert inst == "Acme"
    assert field == "bot_token"


def test_parse_roundtrip():
    original = account_key("google-oauth", "my-project", "client_id")
    svc, inst, field = parse_account_key(original)
    assert account_key(svc, inst, field) == original
