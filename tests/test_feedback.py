"""
tests/test_feedback.py
----------------------
Tests for core/feedback.py  (Phase 2 — feedback generation).
"""

import pytest

from core.melody import compare
from core.feedback import generate_feedback


REF = [60, 62, 64, 65, 67]  # C D E F G


# ── Helper ────────────────────────────────────────────────────────────────────

def feedback(performed, ref=None, mode="exact", input_type="keyboard"):
    r = ref or REF
    results = compare(r, [float(p) for p in performed], mode=mode)
    return generate_feedback(results, input_type=input_type, shift_used=results.shift_used)


# ── Score sentence ────────────────────────────────────────────────────────────

class TestScoreSentence:
    def test_perfect_starts_with_score(self):
        text = feedback(REF)
        assert text.startswith("You played 5 of 5 notes correctly.")

    def test_singing_uses_sang(self):
        text = feedback(REF, input_type="singing")
        assert "You sang 5 of 5 notes correctly." in text

    def test_one_wrong_score(self):
        wrong = list(REF)
        wrong[3] = 66   # F# instead of F
        text = feedback(wrong)
        assert "You played 4 of 5 notes correctly." in text


# ── Note name spelling ────────────────────────────────────────────────────────

class TestNoteNameSpelling:
    def test_sharp_spelled_out(self):
        # Play F# (66) instead of F (65) at position 4
        wrong = list(REF)
        wrong[3] = 66
        text = feedback(wrong)
        # "F#" must never appear; "F sharp" must appear
        assert "#" not in text
        assert "sharp" in text

    def test_no_symbols_in_output(self):
        wrong = list(REF)
        wrong[0] = 61   # C# instead of C
        text = feedback(wrong)
        assert "#" not in text


# ── Error descriptions ────────────────────────────────────────────────────────

class TestErrorDescriptions:
    def test_wrong_note_mentions_expected(self):
        wrong = list(REF)
        wrong[3] = 66  # F# instead of F
        text = feedback(wrong)
        assert "expected" in text.lower()

    def test_missing_note_mentioned(self):
        # Skip C (first note)
        text = feedback(REF[1:])
        assert "missed" in text.lower()

    def test_extra_note_mentioned(self):
        extra = list(REF) + [72]  # add C5 at end
        text = feedback(extra)
        assert "extra" in text.lower()


# ── Empty performance hints ───────────────────────────────────────────────────

class TestEmptyPerformance:
    def test_keyboard_hint(self):
        results = compare(REF, [])
        text = generate_feedback(results, input_type="keyboard")
        assert "Nothing was detected" in text
        assert "MIDI" in text or "keyboard" in text.lower()

    def test_singing_hint(self):
        results = compare(REF, [])
        text = generate_feedback(results, input_type="singing")
        assert "Nothing was detected" in text
        assert "microphone" in text.lower()


# ── Singing cents feedback ────────────────────────────────────────────────────

class TestSingingCentsFeedback:
    def test_high_note_says_higher(self):
        # Sing C4 about 60 cents sharp
        high = [60.0 + 0.6, 62.0, 64.0, 65.0, 67.0]
        text = feedback(high, input_type="singing")
        assert "higher" in text

    def test_low_note_says_lower(self):
        # Sing C4 about 60 cents flat
        low = [60.0 - 0.6, 62.0, 64.0, 65.0, 67.0]
        text = feedback(low, input_type="singing")
        assert "lower" in text

    def test_cents_magnitude_present(self):
        # Should say "about 60 cents higher"
        high = [60.0 + 0.6, 62.0, 64.0, 65.0, 67.0]
        text = feedback(high, input_type="singing")
        assert "cents" in text
        assert "Note 1, C 4" in text

    def test_no_emoji_in_any_output(self):
        text = feedback(REF)
        for ch in text:
            assert ord(ch) < 0x2600 or ch == " ", f"Unexpected character: {repr(ch)}"


# ── Singing verb for extra notes ──────────────────────────────────────────────

class TestSingingVerb:
    def test_extra_note_uses_sang(self):
        extra = list(REF) + [72]  # add C5 at end
        text = feedback(extra, input_type="singing")
        assert "sang" in text
        assert "played an extra" not in text

    def test_extra_at_position_zero_says_at_the_start(self):
        # A note prepended before any reference note lands at position 0
        # (extra note emitted before the first ref note is consumed).
        # Use a tiny ref so the extra lands at position 0.
        results = compare([60], [50.0, 60.0])  # 50 is extra before the match
        text = generate_feedback(results, input_type="singing", shift_used=0)
        assert "at the start" in text


# ── Long melody problem cap ────────────────────────────────────────────────────

REF_LONG = list(range(60, 69))  # 9 notes: C D E F G G# A A# B

class TestLongMelodyCap:
    def test_at_most_3_problems_shown(self):
        # Play all wrong: every note 2 semitones high
        perf = [float(n + 2) for n in REF_LONG]
        text = feedback(perf, ref=REF_LONG)
        # Each "Note X was" sentence counts as a problem; count occurrences
        problem_count = text.count("Note ") + text.count("You missed") + text.count("extra note")
        assert problem_count <= 3

    def test_and_n_more_present_when_many_errors(self):
        # Play all wrong: every note 2 semitones high → 9 errors
        perf = [float(n + 2) for n in REF_LONG]
        text = feedback(perf, ref=REF_LONG)
        assert "more" in text.lower()
    def test_short_melody_no_truncation(self):
        # A 5-note melody with problems should NOT be truncated
        wrong = list(REF)
        wrong[0] = REF[0] + 2
        wrong[1] = REF[1] + 2
        wrong[2] = REF[2] + 2
        wrong[3] = REF[3] + 2
        text = feedback(wrong)
        # Every problem sentence should appear, with no "And N more" cut-off
        assert "missed note 1" in text
        assert "extra note" in text
        assert "Note 4 was" in text
        assert "more" not in text.lower()
    
# ── Relative mode key-offset sentence ────────────────────────────────────────

class TestRelativeShiftFeedback:
    def test_shift_sentence_when_higher(self):
        # Sing 1 semitone higher: shift_used will be -1 (we shifted down by 1)
        perf = [float(n + 1) for n in REF]
        text = feedback(perf, mode="relative", input_type="singing")
        assert "higher" in text
        assert "semitone" in text
        assert "written key" in text

    def test_shift_sentence_when_lower(self):
        # Sing 1 semitone lower: shift_used will be +1
        perf = [float(n - 1) for n in REF]
        text = feedback(perf, mode="relative", input_type="singing")
        assert "lower" in text
        assert "written key" in text

    def test_no_shift_sentence_when_in_key(self):
        # Sing in the exact key: shift_used == 0, no offset sentence
        perf = [float(n) for n in REF]
        text = feedback(perf, mode="relative", input_type="singing")
        assert "written key" not in text
