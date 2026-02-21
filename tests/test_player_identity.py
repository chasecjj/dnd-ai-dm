"""
Unit tests for tools/player_identity.py — PLAYER_MAP resolution.

Pure Python, no Discord dependency. Uses mock objects for author resolution.
"""

from tools.player_identity import (
    init_player_map,
    resolve_character_name,
    resolve_from_message_author,
    get_player_map,
)


def _reset_map(entries: dict):
    """Helper to reset the module-level map for each test."""
    init_player_map(entries)


class TestInitAndResolve:
    """Test init_player_map and resolve_character_name."""

    def test_exact_match(self):
        _reset_map({"ember": "Hadrian Goldhammer"})
        assert resolve_character_name("ember") == "Hadrian Goldhammer"

    def test_case_insensitive(self):
        _reset_map({"ember": "Hadrian Goldhammer"})
        assert resolve_character_name("Ember") == "Hadrian Goldhammer"
        assert resolve_character_name("EMBER") == "Hadrian Goldhammer"
        assert resolve_character_name("eMbEr") == "Hadrian Goldhammer"

    def test_multiple_entries(self):
        _reset_map({
            "ember": "Hadrian Goldhammer",
            "derienkrause": "Kallisar Voidcaller",
        })
        assert resolve_character_name("ember") == "Hadrian Goldhammer"
        assert resolve_character_name("derienkrause") == "Kallisar Voidcaller"

    def test_no_match_returns_none(self):
        _reset_map({"ember": "Hadrian Goldhammer"})
        assert resolve_character_name("unknown_user") is None

    def test_none_candidate_skipped(self):
        _reset_map({"ember": "Hadrian Goldhammer"})
        assert resolve_character_name(None, "ember") == "Hadrian Goldhammer"

    def test_first_match_wins(self):
        """When multiple candidates match, the first one in priority order wins."""
        _reset_map({
            "ember": "Hadrian Goldhammer",
            "ember_alt": "Alt Character",
        })
        # "ember" is tried first and matches
        assert resolve_character_name("ember", "ember_alt") == "Hadrian Goldhammer"

    def test_prefix_match_fallback(self):
        """If exact match fails, prefix match kicks in."""
        _reset_map({"ember": "Hadrian Goldhammer"})
        # "ember0100" starts with "ember"
        assert resolve_character_name("ember0100") == "Hadrian Goldhammer"

    def test_prefix_match_reverse(self):
        """Map key starts with the candidate."""
        _reset_map({"derienkrause": "Kallisar Voidcaller"})
        # "derien" is a prefix of "derienkrause"
        assert resolve_character_name("derien") == "Kallisar Voidcaller"

    def test_empty_map_returns_none(self):
        _reset_map({})
        assert resolve_character_name("ember") is None

    def test_whitespace_stripped(self):
        _reset_map({"ember": "Hadrian Goldhammer"})
        assert resolve_character_name("  ember  ") == "Hadrian Goldhammer"


class TestResolveFromMessageAuthor:
    """Test the Discord author resolver wrapper."""

    def _make_author(self, name=None, global_name=None, display_name=None, nick=None):
        """Create a mock author object with Discord-like attributes."""
        author = type("MockAuthor", (), {
            "name": name,
            "global_name": global_name,
            "display_name": display_name,
            "nick": nick,
        })()
        return author

    def test_resolves_by_name(self):
        _reset_map({"ember": "Hadrian Goldhammer"})
        author = self._make_author(name="ember", global_name="Other", display_name="Other")
        assert resolve_from_message_author(author) == "Hadrian Goldhammer"

    def test_fallback_to_global_name(self):
        _reset_map({"ember": "Hadrian Goldhammer"})
        author = self._make_author(name="xyz123", global_name="ember", display_name="Something")
        assert resolve_from_message_author(author) == "Hadrian Goldhammer"

    def test_fallback_to_display_name(self):
        _reset_map({"ember": "Hadrian Goldhammer"})
        author = self._make_author(name="xyz123", global_name="abc456", display_name="ember")
        assert resolve_from_message_author(author) == "Hadrian Goldhammer"

    def test_fallback_to_nick(self):
        _reset_map({"ember": "Hadrian Goldhammer"})
        author = self._make_author(name="xyz123", global_name="abc456", display_name="def789", nick="ember")
        assert resolve_from_message_author(author) == "Hadrian Goldhammer"

    def test_no_match_returns_none(self):
        _reset_map({"ember": "Hadrian Goldhammer"})
        author = self._make_author(name="unknown", global_name="unknown2", display_name="unknown3")
        assert resolve_from_message_author(author) is None

    def test_handles_missing_attributes(self):
        """Objects without all attributes should still work via getattr."""
        _reset_map({"ember": "Hadrian Goldhammer"})
        # Object with only .name
        author = type("MinimalAuthor", (), {"name": "ember"})()
        assert resolve_from_message_author(author) == "Hadrian Goldhammer"


class TestGetPlayerMap:
    """Test get_player_map returns a copy."""

    def test_returns_copy(self):
        _reset_map({"ember": "Hadrian"})
        m = get_player_map()
        assert m == {"ember": "Hadrian"}
        # Mutating the copy shouldn't affect the original
        m["hacker"] = "Evil Character"
        assert "hacker" not in get_player_map()

    def test_keys_lowercased(self):
        _reset_map({"Ember": "Hadrian", "DerienKrause": "Kallisar"})
        m = get_player_map()
        assert "ember" in m
        assert "derienkrause" in m
        assert "Ember" not in m
