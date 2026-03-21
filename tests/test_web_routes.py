"""Tests for Quest Mirror REST API routes.

All bot managers are mocked via monkeypatching the getter functions
in web.routes so that no real bot initialization or database connection
is required.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def _temp_vault():
    """Create a temporary vault directory with party files."""
    base = tempfile.mkdtemp(prefix="qm_test_")
    party_dir = os.path.join(base, "01 - Party")
    os.makedirs(party_dir)
    with open(os.path.join(party_dir, "Kallisar.md"), "w") as f:
        f.write("---\nname: Kallisar\nrace: Elf\n---\n")
    with open(os.path.join(party_dir, "Brynn.md"), "w") as f:
        f.write("---\nname: Brynn\nrace: Dwarf\n---\n")
    yield base
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture()
def client(monkeypatch, _temp_vault):
    """Create a TestClient with fully mocked bot managers."""

    # -- Vault mock ----------------------------------------------------------
    mock_vault = MagicMock()
    mock_vault.vault_path = _temp_vault

    mock_vault.list_files.return_value = [
        "01 - Party/Kallisar.md",
        "01 - Party/Brynn.md",
    ]
    mock_vault.read_file.side_effect = lambda fpath: (
        ({"name": "Kallisar", "race": "Elf", "class": "Ranger", "level": 5}, "Character body text")
        if "Kallisar" in fpath
        else ({"name": "Brynn", "race": "Dwarf", "class": "Cleric", "level": 4}, "Character body text")
    )
    mock_vault.read_world_clock.return_value = {
        "current_location": "Waterdeep Market",
        "session": 12,
    }

    # -- State manager mock --------------------------------------------------
    mock_state_manager = MagicMock()
    mock_state_manager.is_connected = False
    mock_state_manager.get_character = AsyncMock(return_value=None)
    mock_state_manager.get_all_characters = AsyncMock(return_value=[])

    # -- Solo manager mock ---------------------------------------------------
    mock_solo_manager = MagicMock()
    mock_solo_manager.all_active.return_value = []

    async def fake_start_web_session(character_name, current_location, session_number):
        """Simulate start_web_session returning a SoloSession-like object."""
        from tools.solo_session import SoloSession

        return SoloSession(
            discord_user_id=0,
            thread_id=-1,
            character_name=character_name,
            current_location=current_location,
            session_number=session_number,
        )

    mock_solo_manager.start_web_session = AsyncMock(side_effect=fake_start_web_session)
    mock_solo_manager.get_by_session_id.return_value = None

    # -- Context assembler mock ----------------------------------------------
    mock_context_assembler = MagicMock()
    mock_context_assembler.current_session = 12

    # -- Monkeypatch getter functions ----------------------------------------
    monkeypatch.setattr("web.routes._get_vault", lambda: mock_vault)
    monkeypatch.setattr("web.routes._get_state_manager", lambda: mock_state_manager)
    monkeypatch.setattr("web.routes._get_solo_manager", lambda: mock_solo_manager)
    monkeypatch.setattr("web.routes._get_context_assembler", lambda: mock_context_assembler)

    from web.app import create_app

    app = create_app()
    test_client = TestClient(app)

    # Attach mocks for per-test customization
    test_client._mock_vault = mock_vault
    test_client._mock_state_manager = mock_state_manager
    test_client._mock_solo_manager = mock_solo_manager
    test_client._mock_context_assembler = mock_context_assembler

    return test_client


# ---------------------------------------------------------------------------
# GET /api/characters
# ---------------------------------------------------------------------------


class TestListCharacters:
    def test_returns_200_with_list(self, client) -> None:
        resp = client.get("/api/characters")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_character_names_from_vault(self, client) -> None:
        resp = client.get("/api/characters")
        names = [c["name"] for c in resp.json()]
        assert "Kallisar" in names
        assert "Brynn" in names

    def test_source_is_vault_when_db_disconnected(self, client) -> None:
        resp = client.get("/api/characters")
        for char in resp.json():
            assert char["source"] == "vault"

    def test_merges_db_stats_when_connected(self, client) -> None:
        client._mock_state_manager.is_connected = True
        client._mock_state_manager.get_all_characters.return_value = [
            {"name": "Kallisar", "hp_current": 45, "hp_max": 50, "ac": 16, "level": 5},
        ]
        resp = client.get("/api/characters")
        data = resp.json()
        kallisar = next(c for c in data if c["name"] == "Kallisar")
        assert kallisar["source"] == "vault+db"
        assert kallisar["hp_current"] == 45
        assert kallisar["ac"] == 16

    def test_empty_party_dir(self, client) -> None:
        # Point vault_path to a dir with no Party folder
        empty = tempfile.mkdtemp(prefix="qm_empty_")
        try:
            client._mock_vault.vault_path = empty
            resp = client.get("/api/characters")
            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            shutil.rmtree(empty, ignore_errors=True)


# ---------------------------------------------------------------------------
# GET /api/characters/{name}
# ---------------------------------------------------------------------------


class TestGetCharacter:
    def test_found_in_vault(self, client) -> None:
        resp = client.get("/api/characters/Kallisar")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Kallisar"
        assert data["source"] == "vault"

    def test_not_found_returns_404(self, client) -> None:
        resp = client.get("/api/characters/Nobody")
        assert resp.status_code == 404

    def test_db_preferred_when_connected(self, client) -> None:
        client._mock_state_manager.is_connected = True
        client._mock_state_manager.get_character.return_value = {
            "name": "Kallisar",
            "hp_current": 45,
            "level": 5,
        }
        resp = client.get("/api/characters/Kallisar")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "db"
        assert data["hp_current"] == 45


# ---------------------------------------------------------------------------
# GET /api/solo/sessions
# ---------------------------------------------------------------------------


class TestListSessions:
    def test_returns_200_with_empty_list(self, client) -> None:
        resp = client.get("/api/solo/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_sessions(self, client) -> None:
        from tools.solo_session import SoloSession

        session = SoloSession(
            discord_user_id=123,
            thread_id=-1,
            character_name="Kallisar",
            current_location="Waterdeep",
            session_number=12,
            chaos_factor=7,
        )
        client._mock_solo_manager.all_active.return_value = [session]

        resp = client.get("/api/solo/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["character_name"] == "Kallisar"
        assert data[0]["chaos_factor"] == 7
        assert data[0]["is_web"] is True  # thread_id <= 0

    def test_discord_session_not_web(self, client) -> None:
        from tools.solo_session import SoloSession

        session = SoloSession(
            discord_user_id=123,
            thread_id=999999999999,
            character_name="Brynn",
            current_location="Tavern",
            session_number=12,
        )
        client._mock_solo_manager.all_active.return_value = [session]

        resp = client.get("/api/solo/sessions")
        data = resp.json()
        assert data[0]["is_web"] is False


# ---------------------------------------------------------------------------
# POST /api/solo/sessions
# ---------------------------------------------------------------------------


class TestCreateSession:
    def test_valid_body_returns_200(self, client) -> None:
        resp = client.post("/api/solo/sessions", json={"character_name": "Kallisar"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["character_name"] == "Kallisar"
        assert data["is_web"] is True
        assert "id" in data

    def test_missing_character_name_returns_422(self, client) -> None:
        # Pydantic validation kicks in before our handler for missing field
        resp = client.post("/api/solo/sessions", json={})
        assert resp.status_code == 422

    def test_empty_character_name_returns_400(self, client) -> None:
        resp = client.post("/api/solo/sessions", json={"character_name": "  "})
        assert resp.status_code == 400

    def test_duplicate_returns_409(self, client) -> None:
        client._mock_solo_manager.start_web_session = AsyncMock(return_value=None)
        resp = client.post("/api/solo/sessions", json={"character_name": "Kallisar"})
        assert resp.status_code == 409

    def test_uses_world_clock_location(self, client) -> None:
        resp = client.post("/api/solo/sessions", json={"character_name": "Kallisar"})
        data = resp.json()
        assert data["current_location"] == "Waterdeep Market"

    def test_fallback_location_on_error(self, client) -> None:
        client._mock_vault.read_world_clock.side_effect = Exception("vault error")
        resp = client.post("/api/solo/sessions", json={"character_name": "Kallisar"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_location"] == "The Yawning Portal"


# ---------------------------------------------------------------------------
# GET /api/solo/sessions/{session_id}/history
# ---------------------------------------------------------------------------


class TestSessionHistory:
    def test_not_found_returns_404(self, client) -> None:
        resp = client.get("/api/solo/sessions/nonexistent-uuid/history")
        assert resp.status_code == 404

    def test_returns_narratives(self, client) -> None:
        from tools.solo_session import SoloSession

        session = SoloSession(
            discord_user_id=0,
            thread_id=-1,
            character_name="Kallisar",
            current_location="Waterdeep",
            session_number=12,
            recent_narratives=[
                {"turn": 1, "player_input": "I look around", "narrative": "You see a tavern."},
                {"turn": 2, "player_input": "I enter", "narrative": "The door creaks open."},
            ],
        )
        client._mock_solo_manager.get_by_session_id.return_value = session

        resp = client.get(f"/api/solo/sessions/{session.id}/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session.id
        assert data["character_name"] == "Kallisar"
        assert len(data["recent_narratives"]) == 2
        assert data["recent_narratives"][0]["narrative"] == "You see a tavern."
