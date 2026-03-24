"""Tests for CLI commands: audit, env, flag, unflag, add, set."""
import pytest
from unittest.mock import MagicMock
from click.testing import CliRunner
from creds.cli import main
from creds.registry import Service, Field
from creds.keychain import KeychainItemNotFound


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_store(mocker):
    store = MagicMock()
    mocker.patch("creds.cli.Store", return_value=store)
    return store


@pytest.fixture
def mock_meta(mocker):
    meta = MagicMock()
    meta.setting.return_value = "90"
    meta.get.return_value = None
    meta.all_for_service.return_value = []
    mocker.patch("creds.cli.MetaStore", return_value=meta)
    return meta


@pytest.fixture
def mock_registry(mocker):
    svc_single = Service(
        id="anthropic", label="Anthropic", category="LLM",
        fields=[Field(id="api_key", label="API Key", env_var="ANTHROPIC_API_KEY")],
        required=True,
    )
    svc_multi = Service(
        id="slack", label="Slack", category="Productivity",
        fields=[Field(id="bot_token", label="Bot Token", env_var="SLACK_BOT_TOKEN")],
        multi_instance=True,
    )
    registry = MagicMock()
    registry.all.return_value = [svc_single, svc_multi]
    registry.get.return_value = svc_single
    mocker.patch("creds.cli.Registry", return_value=registry)
    return registry


class TestAudit:
    def test_audit_shows_services(self, runner, mock_store, mock_meta, mock_registry):
        mock_store.exists.return_value = False
        result = runner.invoke(main, ["audit"])
        assert result.exit_code == 0
        assert "Anthropic" in result.output
        assert "Slack" in result.output

    def test_audit_missing_flag_shows_only_unset(self, runner, mock_store, mock_meta, mock_registry):
        mock_store.exists.return_value = True
        result = runner.invoke(main, ["audit", "--missing"])
        assert result.exit_code == 0
        # all are "set" so missing filter leaves nothing
        assert "Anthropic" not in result.output

    def test_audit_quiet_exits_1_when_issues(self, runner, mock_store, mock_meta, mock_registry):
        mock_store.exists.return_value = False
        result = runner.invoke(main, ["audit", "--quiet"])
        assert result.exit_code == 1

    def test_audit_quiet_exits_0_when_all_set(self, runner, mock_store, mock_meta, mock_registry):
        mock_store.exists.return_value = True
        result = runner.invoke(main, ["audit", "--quiet"])
        assert result.exit_code == 0


class TestEnv:
    def test_env_outputs_export_statements(self, runner, mock_store, mock_meta, mock_registry):
        mock_store.exists.return_value = True
        mock_store.get.return_value = "sk-ant-123"
        result = runner.invoke(main, ["env"])
        assert result.exit_code == 0
        assert "export ANTHROPIC_API_KEY=" in result.output

    def test_env_skips_missing_credentials(self, runner, mock_store, mock_meta, mock_registry):
        mock_store.exists.return_value = False
        result = runner.invoke(main, ["env"])
        assert result.exit_code == 0
        assert "ANTHROPIC_API_KEY" not in result.output


class TestFlag:
    def test_flag_calls_meta_flag(self, runner, mock_meta, mock_registry):
        result = runner.invoke(main, ["flag", "anthropic", "--reason", "401"])
        assert result.exit_code == 0
        mock_meta.flag.assert_called_once()

    def test_unflag_calls_meta_unflag(self, runner, mock_meta, mock_registry):
        result = runner.invoke(main, ["unflag", "anthropic"])
        assert result.exit_code == 0
        mock_meta.unflag.assert_called_once()


class TestGet:
    def test_get_outputs_value_to_stdout(self, runner, mock_store):
        mock_store.get.return_value = "sk-ant-123"
        result = runner.invoke(main, ["get", "anthropic"])
        assert result.exit_code == 0
        assert result.output == "sk-ant-123"

    def test_get_exits_1_if_missing(self, runner, mock_store):
        mock_store.get.side_effect = KeychainItemNotFound("not found")
        result = runner.invoke(main, ["get", "anthropic"])
        assert result.exit_code == 1


class TestSet:
    def test_set_calls_store_set(self, runner, mock_store, mock_registry):
        result = runner.invoke(main, ["set", "anthropic", "sk-ant-abc"])
        assert result.exit_code == 0
        mock_store.set.assert_called_once_with(
            "anthropic", "", "api_key", "sk-ant-abc", context="personal"
        )
