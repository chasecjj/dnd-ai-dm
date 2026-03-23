import pytest
from pydantic import ValidationError
from models.mood_assessment import MoodAssessment


class TestMoodAssessment:
    def test_defaults(self):
        mood = MoodAssessment(
            primary_mood="neutral",
            intensity=5,
            environmental_tone="calm",
        )
        assert mood.primary_mood == "neutral"
        assert mood.intensity == 5
        assert mood.secondary_mood is None
        assert mood.npc_emotional_states == {}
        assert mood.typography_hint == "neutral"
        assert mood.breath_timing == "neutral"

    def test_full_combat_mood(self):
        mood = MoodAssessment(
            primary_mood="combat",
            intensity=8,
            secondary_mood="tension",
            npc_emotional_states={"Grigor": "panicked, aggressive"},
            environmental_tone="oppressive fog, clanging steel",
            typography_hint="combat",
            breath_timing="urgent",
        )
        assert mood.primary_mood == "combat"
        assert mood.intensity == 8
        assert mood.npc_emotional_states["Grigor"] == "panicked, aggressive"

    def test_intensity_bounds(self):
        with pytest.raises(ValidationError):
            MoodAssessment(
                primary_mood="neutral", intensity=0,
                environmental_tone="calm",
            )
        with pytest.raises(ValidationError):
            MoodAssessment(
                primary_mood="neutral", intensity=11,
                environmental_tone="calm",
            )

    def test_invalid_primary_mood(self):
        with pytest.raises(ValidationError):
            MoodAssessment(
                primary_mood="excited", intensity=5,
                environmental_tone="calm",
            )

    def test_invalid_secondary_mood(self):
        with pytest.raises(ValidationError):
            MoodAssessment(
                primary_mood="neutral", intensity=5,
                secondary_mood="excited",
                environmental_tone="calm",
            )

    def test_model_dump_roundtrip(self):
        mood = MoodAssessment(
            primary_mood="horror", intensity=7,
            environmental_tone="damp stone",
            typography_hint="horror",
            breath_timing="slow",
        )
        data = mood.model_dump()
        restored = MoodAssessment.model_validate(data)
        assert restored == mood

    def test_model_validate_json(self):
        json_str = '{"primary_mood":"wonder","intensity":6,"environmental_tone":"sunlit clearing","typography_hint":"wonder","breath_timing":"generous"}'
        mood = MoodAssessment.model_validate_json(json_str)
        assert mood.primary_mood == "wonder"
        assert mood.breath_timing == "generous"
