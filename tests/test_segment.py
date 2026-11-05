"""
tests/test_segment.py
---------------------
Tests for core/segment.py  (Phase 5 — note segmentation).

All audio is generated synthetically; no microphone is used.
"""

import math
import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from core.pitch import PitchResult, track_pitch
from core.segment import segment_notes


SAMPLE_RATE = 22050


def midi_to_hz(midi: float) -> float:
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


def make_note_audio(freq_hz: float, duration: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Generate a sine tone with 10 ms fade-in/out."""
    n = int(duration * sr)
    t = np.arange(n) / sr
    audio = 0.8 * np.sin(2 * np.pi * freq_hz * t)
    fade = int(0.01 * sr)  # 10 ms
    audio[:fade] *= np.linspace(0, 1, fade)
    audio[-fade:] *= np.linspace(1, 0, fade)
    return audio.astype(np.float32)


def make_silence(duration: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    return np.zeros(int(duration * sr), dtype=np.float32)


def write_melody_wav(notes_hz: list[float], note_dur: float, gap_dur: float,
                     path: Path, sr: int = SAMPLE_RATE) -> None:
    """Write a series of tones with silent gaps between them."""
    segments = []
    for i, freq in enumerate(notes_hz):
        segments.append(make_note_audio(freq, note_dur, sr))
        if i < len(notes_hz) - 1:
            segments.append(make_silence(gap_dur, sr))
    audio = np.concatenate(segments)
    sf.write(str(path), audio, sr)


# ── Helper to name detected notes ────────────────────────────────────────────

def note_names(notes) -> list[str]:
    return [n.note_name for n in notes]


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestFourNoteScale:
    """C4 D4 E4 F4 with short gaps → 4 notes with correct names."""

    @pytest.fixture
    def four_notes(self, tmp_path):
        freqs = [midi_to_hz(m) for m in [60, 62, 64, 65]]
        wav = tmp_path / "cdef.wav"
        # 0.5 s notes, 0.15 s gaps (> UNVOICED_GAP_MS = 80 ms)
        write_melody_wav(freqs, note_dur=0.5, gap_dur=0.15, path=wav)
        result = track_pitch(wav)
        return segment_notes(result)

    def test_four_notes_detected(self, four_notes):
        assert len(four_notes) == 4, f"Expected 4 notes, got {len(four_notes)}: {note_names(four_notes)}"

    def test_note_names_correct(self, four_notes):
        assert note_names(four_notes) == ["C4", "D4", "E4", "F4"]


class TestFourNoteScaleWithVibrato:
    """Same melody with ±20 cent vibrato; should still detect 4 notes."""

    def test_vibrato_four_notes(self, tmp_path):
        sr = SAMPLE_RATE
        note_dur = 0.5
        gap_dur = 0.15
        midi_notes = [60, 62, 64, 65]

        segments = []
        for i, midi in enumerate(midi_notes):
            centre = midi_to_hz(midi)
            n = int(note_dur * sr)
            t = np.arange(n) / sr
            vibrato = 0.20 * np.sin(2 * np.pi * 5 * t)  # ±20 cents at 5 Hz
            freq_t = centre * (2.0 ** (vibrato / 12.0))
            phase = 2 * np.pi * np.cumsum(freq_t) / sr
            tone = (0.8 * np.sin(phase)).astype(np.float32)
            fade = int(0.01 * sr)
            tone[:fade] *= np.linspace(0, 1, fade)
            tone[-fade:] *= np.linspace(1, 0, fade)
            segments.append(tone)
            if i < len(midi_notes) - 1:
                segments.append(make_silence(gap_dur, sr))

        audio = np.concatenate(segments)
        wav = tmp_path / "cdef_vibrato.wav"
        sf.write(str(wav), audio, sr)

        result = track_pitch(wav)
        notes = segment_notes(result)
        assert len(notes) == 4, f"Expected 4 notes, got {len(notes)}: {note_names(notes)}"
        # Vibrato must not shift the detected note name — exact names are required
        assert note_names(notes) == ["C4", "D4", "E4", "F4"], (
            f"Expected ['C4', 'D4', 'E4', 'F4'], got {note_names(notes)}"
        )


class TestFourNoteScaleWithNoise:
    """Same melody with white noise added; should still detect 4 notes."""

    def test_noisy_four_notes(self, tmp_path):
        freqs = [midi_to_hz(m) for m in [60, 62, 64, 65]]
        wav = tmp_path / "cdef_noisy.wav"
        write_melody_wav(freqs, note_dur=0.5, gap_dur=0.15, path=wav)

        # Add noise to the written file
        audio, sr = sf.read(str(wav), dtype="float32")
        rng = np.random.default_rng(99)
        audio += rng.normal(0, 0.04, len(audio)).astype(np.float32)
        sf.write(str(wav), audio, sr)

        result = track_pitch(wav)
        notes = segment_notes(result)
        assert len(notes) == 4, f"Expected 4 notes, got {len(notes)}: {note_names(notes)}"


class TestRepeatedNote:
    """Two repeated C4 notes with a gap → should give 2 separate notes."""

    def test_two_c4(self, tmp_path):
        freqs = [midi_to_hz(60), midi_to_hz(60)]   # C4, C4
        wav = tmp_path / "c4c4.wav"
        write_melody_wav(freqs, note_dur=0.5, gap_dur=0.15, path=wav)

        result = track_pitch(wav)
        notes = segment_notes(result)
        assert len(notes) == 2, f"Expected 2 notes, got {len(notes)}: {note_names(notes)}"
        assert notes[0].note_name == "C4"
        assert notes[1].note_name == "C4"

    def test_same_pitch_repeated_after_single_frame_articulation(self):
        # A one-hop unvoiced gap is about 23 ms at the production hop size.
        times = np.arange(44, dtype=float) * (512 / 22050)
        freqs = np.full(len(times), midi_to_hz(60), dtype=float)
        voiced = np.ones(len(times), dtype=bool)
        voiced[22] = False
        freqs[22] = np.nan

        notes = segment_notes(PitchResult(times=times, freqs=freqs, voiced=voiced))
        assert note_names(notes) == ["C4", "C4"]
