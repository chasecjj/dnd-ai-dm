"""Tests for Quest Mirror passphrase-based auth module."""

import secrets

import pytest

from web.auth import (
    _active_tokens,
    check_passphrase,
    clear_all_tokens,
    generate_token,
    revoke_token,
    validate_token,
)


@pytest.fixture(autouse=True)
def _clean_tokens():
    """Ensure token set is empty before and after each test."""
    clear_all_tokens()
    yield
    clear_all_tokens()


class TestGenerateToken:
    """Tests for generate_token()."""

    def test_returns_64_char_hex_string(self):
        token = generate_token()
        assert len(token) == 64
        assert all(c in "0123456789abcdef" for c in token)

    def test_generates_unique_tokens(self):
        tokens = {generate_token() for _ in range(100)}
        assert len(tokens) == 100


class TestCheckPassphrase:
    """Tests for check_passphrase()."""

    def test_correct_passphrase_returns_token(self, monkeypatch):
        monkeypatch.setenv("QUEST_MIRROR_SECRET", "dragon-fire-42")
        token = check_passphrase("dragon-fire-42")
        assert token is not None
        assert len(token) == 64

    def test_correct_passphrase_token_is_active(self, monkeypatch):
        monkeypatch.setenv("QUEST_MIRROR_SECRET", "dragon-fire-42")
        token = check_passphrase("dragon-fire-42")
        assert validate_token(token)

    def test_wrong_passphrase_returns_none(self, monkeypatch):
        monkeypatch.setenv("QUEST_MIRROR_SECRET", "dragon-fire-42")
        result = check_passphrase("wrong-passphrase")
        assert result is None

    def test_empty_passphrase_returns_none(self, monkeypatch):
        monkeypatch.setenv("QUEST_MIRROR_SECRET", "dragon-fire-42")
        result = check_passphrase("")
        assert result is None

    def test_missing_env_var_rejects_all(self, monkeypatch):
        monkeypatch.delenv("QUEST_MIRROR_SECRET", raising=False)
        result = check_passphrase("anything")
        assert result is None

    def test_missing_env_var_rejects_empty(self, monkeypatch):
        monkeypatch.delenv("QUEST_MIRROR_SECRET", raising=False)
        result = check_passphrase("")
        assert result is None


class TestValidateToken:
    """Tests for validate_token()."""

    def test_valid_token_passes(self, monkeypatch):
        monkeypatch.setenv("QUEST_MIRROR_SECRET", "secret")
        token = check_passphrase("secret")
        assert validate_token(token)

    def test_random_token_fails(self):
        random_token = secrets.token_hex(32)
        assert not validate_token(random_token)

    def test_empty_string_fails(self):
        assert not validate_token("")

    def test_none_like_string_fails(self):
        assert not validate_token("None")


class TestRevokeToken:
    """Tests for revoke_token()."""

    def test_revoked_token_no_longer_validates(self, monkeypatch):
        monkeypatch.setenv("QUEST_MIRROR_SECRET", "secret")
        token = check_passphrase("secret")
        assert validate_token(token)
        revoke_token(token)
        assert not validate_token(token)

    def test_revoking_nonexistent_token_is_safe(self):
        # Should not raise
        revoke_token("nonexistent-token")


class TestClearAllTokens:
    """Tests for clear_all_tokens()."""

    def test_clears_all_active_tokens(self, monkeypatch):
        monkeypatch.setenv("QUEST_MIRROR_SECRET", "secret")
        tokens = [check_passphrase("secret") for _ in range(5)]
        assert all(validate_token(t) for t in tokens)
        clear_all_tokens()
        assert not any(validate_token(t) for t in tokens)

    def test_clearing_empty_set_is_safe(self):
        # Should not raise
        clear_all_tokens()
