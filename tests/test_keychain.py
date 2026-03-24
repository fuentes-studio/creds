"""Tests for macOS Keychain wrapper."""
import pytest
from unittest.mock import patch, MagicMock
from creds.keychain import get, set as kc_set, delete, exists, KeychainItemNotFound, KeychainError

SERVICE = "io.creds.store"


def _proc(returncode: int, stdout: str = "", stderr: str = "") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


class TestGet:
    def test_returns_value_on_success(self, mocker):
        mocker.patch("subprocess.run", return_value=_proc(0, "sk-ant-abc123\n"))
        assert get("anthropic.api_key") == "sk-ant-abc123"

    def test_strips_trailing_newline(self, mocker):
        mocker.patch("subprocess.run", return_value=_proc(0, "value\n\n"))
        assert get("anthropic.api_key") == "value"

    def test_raises_not_found_on_exit_44(self, mocker):
        mocker.patch("subprocess.run", return_value=_proc(44, "", "could not be found"))
        with pytest.raises(KeychainItemNotFound):
            get("anthropic.api_key")

    def test_raises_not_found_on_missing_message(self, mocker):
        mocker.patch("subprocess.run", return_value=_proc(1, "", "could not be found in keychain"))
        with pytest.raises(KeychainItemNotFound):
            get("anthropic.api_key")

    def test_raises_keychain_error_on_other_failure(self, mocker):
        mocker.patch("subprocess.run", return_value=_proc(1, "", "permission denied"))
        with pytest.raises(KeychainError):
            get("anthropic.api_key")

    def test_calls_security_with_correct_args(self, mocker):
        mock_run = mocker.patch("subprocess.run", return_value=_proc(0, "val"))
        get("anthropic.api_key")
        args = mock_run.call_args[0][0]
        assert args[0] == "security"
        assert "-s" in args
        assert SERVICE in args
        assert "-a" in args
        assert "anthropic.api_key" in args
        assert "-w" in args


class TestSet:
    def test_deletes_then_adds(self, mocker):
        calls = []
        def fake_run(args, **kwargs):
            calls.append(args[1])
            return _proc(0)
        mocker.patch("subprocess.run", side_effect=fake_run)
        kc_set("anthropic.api_key", "sk-ant-123")
        assert calls[0] == "delete-generic-password"
        assert calls[1] == "add-generic-password"

    def test_raises_on_add_failure(self, mocker):
        mocker.patch("subprocess.run", side_effect=[_proc(44), _proc(1, "", "failed")])
        with pytest.raises(KeychainError):
            kc_set("anthropic.api_key", "bad")


class TestDelete:
    def test_calls_delete(self, mocker):
        mock_run = mocker.patch("subprocess.run", return_value=_proc(0))
        delete("anthropic.api_key")
        assert "delete-generic-password" in mock_run.call_args[0][0]

    def test_raises_not_found_on_failure(self, mocker):
        mocker.patch("subprocess.run", return_value=_proc(44))
        with pytest.raises(KeychainItemNotFound):
            delete("anthropic.api_key")


class TestExists:
    def test_true_when_found(self, mocker):
        mocker.patch("creds.keychain.get", return_value="value")
        assert exists("anthropic.api_key") is True

    def test_false_when_not_found(self, mocker):
        mocker.patch("creds.keychain.get", side_effect=KeychainItemNotFound)
        assert exists("anthropic.api_key") is False
