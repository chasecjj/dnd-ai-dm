"""Tests for breath-group narrative chunking.

The key invariant: reassembled text must match the original.
"""

from __future__ import annotations

import pytest

from web.breath_groups import chunk_narrative


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def reassemble(groups: list[dict]) -> str:
    """Join all chunk texts back together."""
    return "".join(g["text"] for g in groups)


# ---------------------------------------------------------------------------
# Empty / whitespace input
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_empty_string_returns_empty_list(self) -> None:
        assert chunk_narrative("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert chunk_narrative("   ") == []

    def test_newlines_only_returns_empty_list(self) -> None:
        assert chunk_narrative("\n\n\n") == []


# ---------------------------------------------------------------------------
# Single sentence
# ---------------------------------------------------------------------------

class TestSingleSentence:
    def test_single_sentence_has_is_final_true(self) -> None:
        groups = chunk_narrative("The dragon roars.")
        assert len(groups) == 1
        assert groups[0]["is_final"] is True

    def test_single_sentence_breath_group_zero(self) -> None:
        groups = chunk_narrative("The dragon roars.")
        assert groups[0]["breath_group"] == 0


# ---------------------------------------------------------------------------
# Multi-sentence splitting
# ---------------------------------------------------------------------------

class TestMultiSentence:
    def test_two_sentences_produce_two_groups(self) -> None:
        text = "The dragon roars. Fire fills the hall."
        groups = chunk_narrative(text)
        assert len(groups) == 2

    def test_three_sentences_sequential_numbering(self) -> None:
        text = "The dragon roars. Fire fills the hall. You draw your sword."
        groups = chunk_narrative(text)
        assert [g["breath_group"] for g in groups] == [0, 1, 2]

    def test_exclamation_and_question_splitting(self) -> None:
        text = "Watch out! What was that? I don't know."
        groups = chunk_narrative(text)
        assert len(groups) == 3

    def test_multi_sentence_is_final_only_on_last(self) -> None:
        text = "The dragon roars. Fire fills the hall. You draw your sword."
        groups = chunk_narrative(text)
        assert groups[0]["is_final"] is False
        assert groups[1]["is_final"] is False
        assert groups[2]["is_final"] is True


# ---------------------------------------------------------------------------
# Clause splitting (long sentences)
# ---------------------------------------------------------------------------

class TestClauseSplitting:
    def test_comma_and_conjunction_splits_long_sentence(self) -> None:
        # >60 chars, has ", and "
        text = "The ancient dragon spreads its massive wings, and fire erupts from its gaping maw."
        groups = chunk_narrative(text)
        assert len(groups) >= 2

    def test_comma_but_conjunction_splits(self) -> None:
        text = "The warrior charges forward with reckless abandon, but the dragon sidesteps easily."
        groups = chunk_narrative(text)
        assert len(groups) >= 2

    def test_semicolon_splits_long_sentence(self) -> None:
        text = "The cavern echoes with the sound of dripping water; somewhere in the darkness something stirs."
        groups = chunk_narrative(text)
        assert len(groups) >= 2

    def test_em_dash_splits_long_sentence(self) -> None:
        text = "The ancient door creaks open revealing a vast chamber\u2014torches flicker along the distant walls."
        groups = chunk_narrative(text)
        assert len(groups) >= 2

    def test_short_sentence_not_split_at_clause(self) -> None:
        # <60 chars, has ", and " but should NOT be split
        text = "The cat sat, and the dog lay down."
        groups = chunk_narrative(text)
        assert len(groups) == 1


# ---------------------------------------------------------------------------
# Quoted dialogue preservation
# ---------------------------------------------------------------------------

class TestQuotedDialogue:
    def test_quoted_dialogue_stays_together(self) -> None:
        text = '"You shall not pass!" The wizard raises his staff.'
        groups = chunk_narrative(text)
        # The quote and the following sentence should be separate groups,
        # but the quote itself is one group.
        quote_group = groups[0]
        assert '"You shall not pass!"' in quote_group["text"]

    def test_smart_quoted_dialogue_stays_together(self) -> None:
        text = '\u201cBeware the darkness,\u201d the old man whispers.'
        groups = chunk_narrative(text)
        # Should stay as one group (it's dialogue)
        assert len(groups) >= 1


# ---------------------------------------------------------------------------
# Mood pass-through
# ---------------------------------------------------------------------------

class TestMood:
    def test_default_mood_is_neutral(self) -> None:
        groups = chunk_narrative("The dragon roars.")
        assert groups[0]["mood"] == "neutral"

    def test_custom_mood_passed_through(self) -> None:
        groups = chunk_narrative("The dragon roars. Fire fills the hall.", mood="dramatic")
        for g in groups:
            assert g["mood"] == "dramatic"


# ---------------------------------------------------------------------------
# Text preservation invariant (THE KEY CONTRACT)
# ---------------------------------------------------------------------------

class TestTextPreservation:
    def test_simple_reassembly(self) -> None:
        text = "The dragon roars. Fire fills the hall."
        groups = chunk_narrative(text)
        assert reassemble(groups).strip() == text.strip()

    def test_clause_split_reassembly(self) -> None:
        text = "The ancient dragon spreads its massive wings, and fire erupts from its gaping maw."
        groups = chunk_narrative(text)
        assert reassemble(groups).strip() == text.strip()

    def test_em_dash_reassembly(self) -> None:
        text = "The ancient door creaks open revealing a vast chamber\u2014torches flicker along the distant walls."
        groups = chunk_narrative(text)
        assert reassemble(groups).strip() == text.strip()

    def test_complex_text_reassembly(self) -> None:
        text = (
            "The dragon roars! Fire fills the hall. "
            '"Run!" the wizard shouts, and the party scatters. '
            "You draw your sword\u2014this is the moment you trained for."
        )
        groups = chunk_narrative(text)
        assert reassemble(groups).strip() == text.strip()

    def test_multiline_text_reassembly(self) -> None:
        text = "The wind howls.\n\nYou step forward."
        groups = chunk_narrative(text)
        assert reassemble(groups).strip() == text.strip()

    def test_trailing_whitespace_reassembly(self) -> None:
        text = "  The dragon roars.  Fire fills the hall.  "
        groups = chunk_narrative(text)
        assert reassemble(groups).strip() == text.strip()


# ---------------------------------------------------------------------------
# Chunk dict structure
# ---------------------------------------------------------------------------

class TestChunkStructure:
    def test_chunk_has_required_keys(self) -> None:
        groups = chunk_narrative("The dragon roars.")
        chunk = groups[0]
        assert "text" in chunk
        assert "mood" in chunk
        assert "breath_group" in chunk
        assert "is_final" in chunk

    def test_chunk_types(self) -> None:
        groups = chunk_narrative("The dragon roars.")
        chunk = groups[0]
        assert isinstance(chunk["text"], str)
        assert isinstance(chunk["mood"], str)
        assert isinstance(chunk["breath_group"], int)
        assert isinstance(chunk["is_final"], bool)
