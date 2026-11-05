"""
tests/test_notes.py
-------------------
Tests for core/notes.py  (Phase 1).
"""

import math
import pytest

from core.notes import freq_to_midi, midi_to_note_name, note_name_to_midi, cents_off


# ── freq_to_midi ──────────────────────────────────────────────────────────────

class TestFreqToMidi:
    def test_c4(self):
        # Middle C ≈ 261.63 Hz should map to MIDI 60
        result = freq_to_midi(261.63)
        assert abs(result - 60.0) < 0.01, f"Expected ~60, got {result}"

    def test_a4(self):
        # A4 = 440 Hz exactly → MIDI 69.0
        assert freq_to_midi(440.0) == pytest.approx(69.0)

    def test_a0(self):
        # A0 = 27.5 Hz → MIDI 21
        result = freq_to_midi(27.5)
        assert abs(result - 21.0) < 0.01, f"Expected ~21, got {result}"

    def test_c8(self):
        # C8 = 4186 Hz → MIDI 108
        result = freq_to_midi(4186.0)
        assert abs(result - 108.0) < 0.01, f"Expected ~108, got {result}"

    def test_zero_raises(self):
        with pytest.raises(ValueError, match="positive"):
            freq_to_midi(0.0)

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="positive"):
            freq_to_midi(-440.0)

    def test_nan_raises(self):
        with pytest.raises(ValueError, match="NaN"):
            freq_to_midi(float("nan"))

    def test_returns_float(self):
        assert isinstance(freq_to_midi(440.0), float)


# ── midi_to_note_name ─────────────────────────────────────────────────────────

class TestMidiToNoteName:
    def test_c4(self):
        assert midi_to_note_name(60) == "C4"

    def test_a4(self):
        assert midi_to_note_name(69) == "A4"

    def test_a0(self):
        assert midi_to_note_name(21) == "A0"

    def test_c8(self):
        assert midi_to_note_name(108) == "C8"

    def test_sharp(self):
        assert midi_to_note_name(54) == "F#3"

    def test_c_negative_octave(self):
        # MIDI 0 = C in octave -1
        assert midi_to_note_name(0) == "C-1"

    def test_rounds_float(self):
        # A float slightly above 60 should still round to C4
        assert midi_to_note_name(60.1) == "C4"


# ── note_name_to_midi ─────────────────────────────────────────────────────────

class TestNoteNameToMidi:
    def test_c4(self):
        assert note_name_to_midi("C4") == 60

    def test_a4(self):
        assert note_name_to_midi("A4") == 69

    def test_sharp(self):
        assert note_name_to_midi("F#3") == 54

    def test_a0(self):
        assert note_name_to_midi("A0") == 21

    def test_c8(self):
        assert note_name_to_midi("C8") == 108

    def test_bad_pitch_class(self):
        with pytest.raises(ValueError, match="Unknown pitch class"):
            note_name_to_midi("H4")

    def test_bad_octave(self):
        with pytest.raises(ValueError, match="octave"):
            note_name_to_midi("Cxx")

    def test_whitespace_stripped(self):
        assert note_name_to_midi("  C4  ") == 60


# ── Round-trip ────────────────────────────────────────────────────────────────

class TestRoundTrip:
    @pytest.mark.parametrize("name", ["C4", "F#3", "A4", "A0", "C8", "D#5", "G#2"])
    def test_name_to_midi_to_name(self, name):
        midi = note_name_to_midi(name)
        assert midi_to_note_name(midi) == name


# ── cents_off ─────────────────────────────────────────────────────────────────

class TestCentsOff:
    def test_exact_a4(self):
        # 440 Hz is exactly A4, so cents_off should be 0
        assert cents_off(440.0) == pytest.approx(0.0, abs=1e-9)

    def test_exact_c4(self):
        # 261.626 Hz is C4; check it's within 1 cent of 0
        result = cents_off(261.626)
        assert abs(result) < 1.0

    def test_sharp_direction(self):
        # A frequency slightly above A4 should give a positive result
        assert cents_off(445.0) > 0

    def test_flat_direction(self):
        # A frequency slightly below A4 should give a negative result
        assert cents_off(435.0) < 0

    def test_range(self):
        # cents_off must always be in (-50, +50]
        for freq in [100, 200, 300, 440, 880, 1000]:
            result = cents_off(freq)
            assert -50 < result <= 50, f"Out of range for {freq} Hz: {result}"

    def test_zero_raises(self):
        with pytest.raises(ValueError):
            cents_off(0.0)

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            cents_off(-1.0)

    def test_nan_raises(self):
        with pytest.raises(ValueError):
            cents_off(float("nan"))


def test_standard_piano_key_range_contains_88_keys():
    from core.notes import piano_key_numbers, piano_key_names

    numbers = piano_key_numbers()
    names = piano_key_names()
    assert len(numbers) == 88
    assert numbers[0] == 21 and numbers[-1] == 108
    assert names[0] == "A0" and names[-1] == "C8"


def test_flat_note_names_are_accepted():
    assert note_name_to_midi("Bb3") == note_name_to_midi("A#3")
    assert note_name_to_midi("Db4") == note_name_to_midi("C#4")
