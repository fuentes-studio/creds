"""Tests for migration wizard."""
import pytest
from unittest.mock import MagicMock
from creds.migrate import (
    scan_legacy,
    LegacyResult,
    migrate_entry,
    build_migration_plan,
)
from creds.registry import LegacyKey, Service, Field


def _make_service(service_id: str, field_id: str, legacy_keys: list) -> Service:
    return Service(
        id=service_id,
        label=service_id.title(),
        category="Test",
        fields=[Field(id=field_id, label=field_id, env_var=field_id.upper())],
        legacy_keys=legacy_keys,
    )


class TestScanLegacy:
    def test_found_on_first_key(self, mocker):
        """Returns value from first matching legacy key."""
        mocker.patch(
            "creds.migrate.subprocess.run",
            return_value=MagicMock(returncode=0, stdout="sk-ant-123\n", stderr=""),
        )
        svc = _make_service(
            "anthropic", "api_key",
            [LegacyKey(service="claude_api_key", account="claude_api_key")]
        )
        result = scan_legacy(svc)
        assert result is not None
        assert result.value == "sk-ant-123"
        assert result.legacy_key.account == "claude_api_key"

    def test_tries_all_keys_before_giving_up(self, mocker):
        """Tries all legacy keys, returns None if none found."""
        mocker.patch(
            "creds.migrate.subprocess.run",
            return_value=MagicMock(returncode=44, stdout="", stderr="not found"),
        )
        svc = _make_service(
            "cerebras", "api_key",
            [
                LegacyKey(service="com.example.app", account="cerebras-api-key"),
                LegacyKey(service="example-tool", account="cerebras-api-key"),
            ]
        )
        result = scan_legacy(svc)
        assert result is None

    def test_returns_none_when_no_legacy_keys(self):
        svc = _make_service("newservice", "api_key", [])
        result = scan_legacy(svc)
        assert result is None

    def test_tries_second_key_when_first_fails(self, mocker):
        responses = [
            MagicMock(returncode=44, stdout="", stderr="not found"),
            MagicMock(returncode=0, stdout="found-value\n", stderr=""),
        ]
        mocker.patch("creds.migrate.subprocess.run", side_effect=responses)
        svc = _make_service(
            "openai", "api_key",
            [
                LegacyKey(service="openai-api-key", account="openai-api-key"),
                LegacyKey(service="com.example.tool", account="openai-api-key"),
            ]
        )
        result = scan_legacy(svc)
        assert result is not None
        assert result.value == "found-value"
        assert result.legacy_key.service == "com.example.tool"


class TestBuildMigrationPlan:
    def test_returns_found_and_not_found(self, mocker):
        def mock_scan(svc):
            if svc.id == "anthropic":
                return LegacyResult(
                    service=svc,
                    field_id="api_key",
                    value="sk-ant-123",
                    legacy_key=LegacyKey(service="claude_api_key", account="claude_api_key"),
                )
            return None

        mocker.patch("creds.migrate.scan_legacy", side_effect=mock_scan)
        services = [
            _make_service("anthropic", "api_key", [LegacyKey("x", "y")]),
            _make_service("gemini", "api_key", [LegacyKey("a", "b")]),
        ]
        found, not_found = build_migration_plan(services)
        assert len(found) == 1
        assert len(not_found) == 1
        assert found[0].service.id == "anthropic"
        assert not_found[0].id == "gemini"


class TestMigrateEntry:
    def test_writes_to_canonical_keychain(self):
        mock_store = MagicMock()
        result = LegacyResult(
            service=_make_service("anthropic", "api_key", []),
            field_id="api_key",
            value="sk-ant-123",
            legacy_key=LegacyKey(service="claude_api_key", account="claude_api_key"),
        )
        migrate_entry(result, mock_store, context="personal")
        mock_store.set.assert_called_once_with(
            "anthropic", "", "api_key", "sk-ant-123", context="personal"
        )
