import pytest
from pydantic import ValidationError
from models.battle_scar import BattleScar


class TestBattleScar:
    def test_minimal(self):
        scar = BattleScar(face=20, scar_type="nat20", character_name="Hadrian")
        assert scar.face == 20
        assert scar.scar_type == "nat20"
        assert scar.session_id is None

    def test_full(self):
        scar = BattleScar(
            face=1, scar_type="nat1", character_name="Hadrian",
            session_id=3, turn_number=12, created_at="2026-03-22T18:00:00Z",
        )
        assert scar.face == 1
        assert scar.turn_number == 12

    def test_face_bounds(self):
        with pytest.raises(ValidationError):
            BattleScar(face=0, scar_type="nat20", character_name="Hadrian")
        with pytest.raises(ValidationError):
            BattleScar(face=21, scar_type="nat20", character_name="Hadrian")

    def test_invalid_scar_type(self):
        with pytest.raises(ValidationError):
            BattleScar(face=15, scar_type="scratch", character_name="Hadrian")

    def test_roundtrip(self):
        scar = BattleScar(face=20, scar_type="crit_kill", character_name="Hadrian")
        data = scar.model_dump()
        restored = BattleScar.model_validate(data)
        assert restored == scar
