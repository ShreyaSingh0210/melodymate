"""
tests/test_synth.py
-------------------
Tests for core/synth.py  (Phase 6 — WAV synthesis).
"""

import math
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from core.synth import write_melody_wav, NOTE_DURATION, SAMPLE_RATE, SILENCE_MS
from core.pitch import track_pitch
from core.segment import segment_notes
from core.melody import MELODIES


SCALE_MIDI = [60, 62, 64, 65]   # C4 D4 E4 F4


class TestWriteMelodyWav:
    def test_creates_file(self, tmp_path):
        out = tmp_path / "melody.wav"
        write_melody_wav(SCALE_MIDI, out)
        assert out.exists()

    def test_correct_duration(self, tmp_path):
        out = tmp_path / "melody.wav"
        note_dur = 0.5
        n_notes = len(SCALE_MIDI)
        write_melody_wav(SCALE_MIDI, out, note_duration=note_dur)
        audio, sr = sf.read(str(out))
        # Total audio = n_notes * note_dur + (n_notes - 1) * SILENCE_MS/1000
        expected_samples = int(
            (n_notes * note_dur + (n_notes - 1) * SILENCE_MS / 1000.0) * sr
        )
        # Allow 1% tolerance for rounding
        assert abs(len(audio) - expected_samples) < expected_samples * 0.01

    def test_readable_by_soundfile(self, tmp_path):
        out = tmp_path / "melody.wav"
        write_melody_wav(SCALE_MIDI, out)
        audio, sr = sf.read(str(out))
        assert len(audio) > 0
        assert sr > 0

    def test_overwrites_existing(self, tmp_path):
        out = tmp_path / "melody.wav"
        write_melody_wav([60], out)   # first write
        size1 = out.stat().st_size
        write_melody_wav([60, 62], out)  # second write (different content)
        size2 = out.stat().st_size
        assert size2 > size1   # longer melody → bigger file

    def test_no_clipping(self, tmp_path):
        out = tmp_path / "melody.wav"
        write_melody_wav(SCALE_MIDI, out)
        audio, _ = sf.read(str(out), dtype="float32")
        assert np.all(np.abs(audio) <= 1.0), "Audio should not clip"


class TestSynthIntegration:
    """
    Integration test: synthesise a melody, run pitch tracking + segmentation,
    and verify the detected notes match what was written.
    """

    def test_synth_to_segment(self, tmp_path):
        out = tmp_path / "scale.wav"
        # Use a longer note so pYIN has time to stabilise
        write_melody_wav(SCALE_MIDI, out, note_duration=0.8)

        result = track_pitch(out)
        notes = segment_notes(result)

        # Should detect all 4 notes
        assert len(notes) == len(SCALE_MIDI), (
            f"Expected {len(SCALE_MIDI)} notes, got {len(notes)}: "
            f"{[n.note_name for n in notes]}"
        )

        # Each note should be within 1 semitone of the expected pitch
        for i, (note, ref_midi) in enumerate(zip(notes, SCALE_MIDI)):
            assert abs(note.midi_float - ref_midi) < 1.0, (
                f"Note {i+1}: detected {note.note_name} ({note.midi_float:.1f}), "
                f"expected MIDI {ref_midi}"
            )

    def test_mary_lamb(self, tmp_path):
        """Synthesise Mary Had a Little Lamb and detect at least 20 of 25 notes."""
        midi_seq = MELODIES["mary_lamb"]
        out = tmp_path / "mary_lamb.wav"
        write_melody_wav(midi_seq, out, note_duration=0.6)

        result = track_pitch(out)
        notes = segment_notes(result)

        # Generous threshold: accept if most notes are detected (repeated notes
        # make exact count fragile; the key check is rough coverage).
        assert len(notes) >= 20, (
            f"Expected at least 20 of {len(midi_seq)} notes, "
            f"got {len(notes)}: {[n.note_name for n in notes]}"
        )
