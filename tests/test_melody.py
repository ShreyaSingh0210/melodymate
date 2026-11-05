"""
tests/test_melody.py
--------------------
Tests for core/melody.py  (Phase 2 — sequence comparison).
"""

import pytest

from core.melody import compare, CENTS_THRESHOLD, NoteResult, CompareResults


# Helper: reference is C, D, E, F  (MIDI 60, 62, 64, 65)
REF_CDEF = [60, 62, 64, 65]
# Mary lamb first phrase: E D C D E E E
REF_MARY = [64, 62, 60, 62, 64, 64, 64]


# ── Utilities ──────────────────────────────────────────────────────────────────

def labels(results):
    return [r.label for r in results]


# ── Basic correctness ─────────────────────────────────────────────────────────

class TestPerfectPerformance:
    def test_all_correct(self):
        results = compare(REF_CDEF, [60.0, 62.0, 64.0, 65.0])
        assert labels(results) == ["correct", "correct", "correct", "correct"]

    def test_correct_count(self):
        results = compare(REF_CDEF, [60.0, 62.0, 64.0, 65.0])
        assert sum(1 for r in results if r.label == "correct") == 4


class TestOneWrongNote:
    def test_fourth_note_wrong(self):
        # Play G (67) instead of F (65) at position 4
        results = compare(REF_CDEF, [60.0, 62.0, 64.0, 67.0])
        assert results[3].label == "wrong"
        assert results[3].ref_midi == 65

    def test_first_three_still_correct(self):
        results = compare(REF_CDEF, [60.0, 62.0, 64.0, 67.0])
        assert labels(results)[:3] == ["correct", "correct", "correct"]


class TestMissingNotes:
    def test_missing_first_note(self):
        # Skip the first note (C), play D E F
        results = compare(REF_CDEF, [62.0, 64.0, 65.0])
        missing = [r for r in results if r.label == "missing"]
        assert len(missing) == 1
        assert missing[0].ref_midi == 60  # C was missed

    def test_missing_last_note(self):
        # Play C D E, skip F
        results = compare(REF_CDEF, [60.0, 62.0, 64.0])
        missing = [r for r in results if r.label == "missing"]
        assert len(missing) == 1
        assert missing[0].ref_midi == 65  # F was missed

    def test_missing_middle_note(self):
        # Play C D F (skip E)
        results = compare(REF_CDEF, [60.0, 62.0, 65.0])
        missing = [r for r in results if r.label == "missing"]
        assert len(missing) == 1


class TestExtraNote:
    def test_extra_note_detected(self):
        # Play C D E F G (extra G)
        results = compare(REF_CDEF, [60.0, 62.0, 64.0, 65.0, 67.0])
        extras = [r for r in results if r.label == "extra"]
        assert len(extras) == 1
        assert extras[0].perf_midi == 67.0


class TestEmptyPerformance:
    def test_all_missing(self):
        results = compare(REF_CDEF, [])
        assert all(r.label == "missing" for r in results)
        assert len(results) == len(REF_CDEF)

    def test_empty_reference(self):
        results = compare([], [60.0, 62.0])
        assert results == []


# ── The C, D, E, G vs C, D, E, F case ────────────────────────────────────────

class TestCDEGvsCDEF:
    def test_cdeg_against_cdef(self):
        # C D E are correct; G (67) is wrong at position 4 (expected F=65)
        results = compare(REF_CDEF, [60.0, 62.0, 64.0, 67.0])
        assert results[0].label == "correct"   # C
        assert results[1].label == "correct"   # D
        assert results[2].label == "correct"   # E
        assert results[3].label == "wrong"     # G ≠ F


# ── Cents threshold ───────────────────────────────────────────────────────────

class TestCentsThreshold:
    def test_60_cents_high_is_wrong(self):
        # 60 cents > CENTS_THRESHOLD (50), so the note should be wrong
        high_c4 = 60.0 + 60 / 100.0   # 0.6 semitones = 60 cents up
        results = compare([60], [high_c4])
        assert results[0].label == "wrong"

    def test_30_cents_high_is_correct(self):
        # 30 cents ≤ 50, so it's close enough
        slightly_high = 60.0 + 30 / 100.0
        results = compare([60], [slightly_high])
        assert results[0].label == "correct"

    def test_exactly_at_threshold_is_correct(self):
        # Exactly 50 cents should be correct (≤ threshold)
        at_threshold = 60.0 + CENTS_THRESHOLD / 100.0
        results = compare([60], [at_threshold])
        assert results[0].label == "correct"

    def test_cents_error_sign(self):
        # A note sung below should have negative cents_error
        low = 60.0 - 0.3
        results = compare([60], [low])
        assert results[0].cents_error < 0


# ── Modes ─────────────────────────────────────────────────────────────────────

class TestIgnoreOctaveMode:
    def test_octave_lower_correct(self):
        # Melody played an octave lower; pitch classes still match
        perf = [n - 12 for n in REF_CDEF]
        results = compare(REF_CDEF, [float(p) for p in perf], mode="ignore_octave")
        assert all(r.label == "correct" for r in results)

    def test_octave_lower_wrong_exact(self):
        # Same test but in exact mode should produce all wrong
        perf = [n - 12 for n in REF_CDEF]
        results = compare(REF_CDEF, [float(p) for p in perf], mode="exact")
        assert all(r.label == "wrong" for r in results)


class TestRelativeMode:
    def test_octave_lower_correct(self):
        # A melody played an octave lower in relative mode = all correct
        perf = [float(n - 12) for n in REF_CDEF]
        results = compare(REF_CDEF, perf, mode="relative")
        assert all(r.label == "correct" for r in results)
        assert results.shift_used == 12   # shifted +12 to realign

    def test_fourth_higher_correct(self):
        # A fourth = 5 semitones.  Whole melody a 4th higher should align.
        perf = [float(n + 5) for n in REF_CDEF]
        results = compare(REF_CDEF, perf, mode="relative")
        assert all(r.label == "correct" for r in results)
        assert results.shift_used == -5   # shifted -5 to realign

    def test_empty_performance_all_missing(self):
        results = compare(REF_CDEF, [], mode="relative")
        assert all(r.label == "missing" for r in results)

    def test_glitch_first_note_one_semitone_higher(self):
        """
        Whole melody (REF_MARY first phrase) sung 1 semitone higher, but with a
        wrong extra note prepended (simulating a glitch at the start).
        The brute-force shift should ignore the glitch and still find shift=-1,
        and the score should be at least 80 %.
        """
        # REF_MARY = [64, 62, 60, 62, 64, 64, 64]
        melody_1_higher = [float(n + 1) for n in REF_MARY]
        # Prepend a wrong note (MIDI 50, well outside the range)
        glitch_perf = [50.0] + melody_1_higher
        results = compare(REF_MARY, glitch_perf, mode="relative")
        assert isinstance(results, CompareResults)
        assert results.shift_used == -1
        ref_notes = [r for r in results if r.label != "extra"]
        correct = sum(1 for r in ref_notes if r.label == "correct")
        total = len(ref_notes)
        assert correct / total >= 0.8, (
            f"Expected ≥80 % correct in glitch test, got {correct}/{total}"
        )
