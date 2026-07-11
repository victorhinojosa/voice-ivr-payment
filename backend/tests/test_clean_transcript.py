"""
Unit tests for clean_transcript (backend/main.py) — strips STT
sound-caption artifacts like "(clicks mouse)" or "[music playing]".
"""
from voice.formatting import clean_transcript


class TestCleanTranscript:
    def test_strips_parenthetical_sound_caption(self):
        assert clean_transcript("Okay (clicks mouse) I can do that") == "Okay I can do that"

    def test_strips_bracketed_sound_caption(self):
        assert clean_transcript("Sure [music playing] sounds good") == "Sure sounds good"

    def test_strips_caption_at_start(self):
        assert clean_transcript("(background noise) Yes I agree") == "Yes I agree"

    def test_strips_caption_at_end(self):
        assert clean_transcript("Yes I agree (background noise)") == "Yes I agree"

    def test_strips_multiple_captions(self):
        assert clean_transcript("(sighs) I guess [pause] that works") == "I guess that works"

    def test_collapses_resulting_whitespace(self):
        assert clean_transcript("Hello   (noise)   world") == "Hello world"

    def test_no_captions_returns_text_unchanged(self):
        assert clean_transcript("I can pay by Friday") == "I can pay by Friday"

    def test_empty_string_returns_empty_string(self):
        assert clean_transcript("") == ""

    def test_only_caption_returns_empty_string(self):
        assert clean_transcript("(silence)") == ""

    def test_leading_and_trailing_whitespace_trimmed(self):
        assert clean_transcript("  (noise) hello  ") == "hello"
