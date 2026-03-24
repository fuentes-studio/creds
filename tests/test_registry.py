"""Tests for service registry YAML loader."""
import pytest
from pathlib import Path
from creds.registry import Registry, Service, Field

MINIMAL_YAML = """
services:
  - id: anthropic
    label: Anthropic Claude
    category: LLM Providers
    required: true
    fields:
      - id: api_key
        label: API Key
        env_var: ANTHROPIC_API_KEY
        required: true

  - id: slack
    label: Slack
    category: Productivity
    multi_instance: true
    fields:
      - id: bot_token
        label: Bot Token
        env_var: SLACK_BOT_TOKEN
        required: true
      - id: app_token
        label: App Token
        env_var: SLACK_APP_TOKEN
        required: true
"""


@pytest.fixture
def registry(tmp_path):
    f = tmp_path / "services.yaml"
    f.write_text(MINIMAL_YAML)
    return Registry(registry_path=f)


def test_loads_services(registry):
    assert len(registry.all()) == 2


def test_service_fields(registry):
    svc = registry.get("anthropic")
    assert svc is not None
    assert svc.label == "Anthropic Claude"
    assert svc.category == "LLM Providers"
    assert svc.required is True
    assert len(svc.fields) == 1
    assert svc.fields[0].env_var == "ANTHROPIC_API_KEY"


def test_multi_instance_flag(registry):
    slack = registry.get("slack")
    assert slack.multi_instance is True
    assert len(slack.fields) == 2


def test_by_category(registry):
    cats = registry.by_category()
    assert "LLM Providers" in cats
    assert "Productivity" in cats
    assert len(cats["LLM Providers"]) == 1


def test_missing_service_returns_none(registry):
    assert registry.get("nonexistent") is None


def test_default_context_is_personal(registry):
    svc = registry.get("anthropic")
    assert svc.context == "personal"
