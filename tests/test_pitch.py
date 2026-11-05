"""
tests/test_pitch.py
-------------------
Tests for core/pitch.py  (Phase 4 — pitch tracking).

All tests generate synthetic audio with NumPy; no microphone is used.
"""

import math
import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from core.pitch import track_pitch, FMIN_HZ, FMAX_HZ


# ── Helpers ───────────────────────────────────────────────────────────────────

SAMPLE_RATE = 22050   # use a lower SR for faster tests


def midi_to_hz(midi: float) -> float:
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


def hz_to_cents_from_midi(freq: float, midi_ref: int) -> float:
    """Return signed cents between freq and the reference MIDI note."""
    ref_hz = midi_to_hz(midi_ref)
    return 1200.0 * math.log2(freq / ref_hz)


def write_sine_wav(freq_hz: float, duration: float, path: Path, sr: int = SAMPLE_RATE) -> None:
    """Write a pure sine wave to a WAV file."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = 0.8 * np.sin(2 * np.pi * freq_hz * t)
    sf.write(str(path), audio.astype(np.float32), sr)


def write_silence_wav(duration: float, path: Path, sr: int = SAMPLE_RATE) -> None:
    """Write a silent WAV file."""
    audio = np.zeros(int(sr * duration), dtype=np.float32)
    sf.write(str(path), audio, sr)


def median_voiced_freq(result) -> float:
    """Return the median of all voiced frequency frames."""
    voiced_freqs = result.freqs[result.voiced]
    return float(np.median(voiced_freqs))


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestPureTones:
    """pYIN should detect clean sine tones within 20 cents."""

    def test_c4(self, tmp_path):
        freq = midi_to_hz(60)   # C4 = 261.63 Hz
        wav = tmp_path / "c4.wav"
        write_sine_wav(freq, duration=1.0, path=wav)
        result = track_pitch(wav)
        assert result.voiced.any(), "Should have voiced frames"
        detected = median_voiced_freq(result)
        cents = abs(hz_to_cents_from_midi(detected, 60))
        assert cents < 20.0, f"C4 detected {cents:.1f} cents off"

    def test_a4(self, tmp_path):
        freq = midi_to_hz(69)   # A4 = 440 Hz
        wav = tmp_path / "a4.wav"
        write_sine_wav(freq, duration=1.0, path=wav)
        result = track_pitch(wav)
        assert result.voiced.any()
        detected = median_voiced_freq(result)
        cents = abs(hz_to_cents_from_midi(detected, 69))
        assert cents < 20.0, f"A4 detected {cents:.1f} cents off"

    def test_e3(self, tmp_path):
        freq = midi_to_hz(52)   # E3 = 164.81 Hz
        wav = tmp_path / "e3.wav"
        write_sine_wav(freq, duration=1.0, path=wav)
        result = track_pitch(wav)
        assert result.voiced.any()
        detected = median_voiced_freq(result)
        cents = abs(hz_to_cents_from_midi(detected, 52))
        assert cents < 20.0, f"E3 detected {cents:.1f} cents off"


class TestVibrato:
    """A tone with vibrato should still be detected near the centre pitch."""

    def test_c4_with_vibrato(self, tmp_path):
        sr = SAMPLE_RATE
        duration = 2.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)

        # C4 with ±30 cents vibrato at 5 Hz
        centre_hz = midi_to_hz(60)
        # ±30 cents = ±0.3 semitones; in Hz: multiply by 2^(±0.3/12)
        vibrato_semitones = 0.30 * np.sin(2 * np.pi * 5 * t)
        freq_t = centre_hz * (2.0 ** (vibrato_semitones / 12.0))
        # Generate FM sine wave
        phase = 2 * np.pi * np.cumsum(freq_t) / sr
        audio = (0.8 * np.sin(phase)).astype(np.float32)

        wav = tmp_path / "c4_vibrato.wav"
        sf.write(str(wav), audio, sr)

        result = track_pitch(wav)
        assert result.voiced.any()
        detected = median_voiced_freq(result)
        cents = abs(hz_to_cents_from_midi(detected, 60))
        assert cents < 20.0, f"C4+vibrato detected {cents:.1f} cents off"


class TestNoise:
    """A tone with added white noise (~20 dB SNR) should still be detected."""

    def test_c4_with_noise(self, tmp_path):
        sr = SAMPLE_RATE
        duration = 2.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)

        signal = 0.8 * np.sin(2 * np.pi * midi_to_hz(60) * t)
        # 20 dB SNR: noise RMS = signal RMS / 10
        noise = np.random.default_rng(42).normal(0, 0.08 * 0.707, len(t))
        audio = (signal + noise).astype(np.float32)

        wav = tmp_path / "c4_noisy.wav"
        sf.write(str(wav), audio, sr)

        result = track_pitch(wav)
        assert result.voiced.any()
        detected = median_voiced_freq(result)
        cents = abs(hz_to_cents_from_midi(detected, 60))
        assert cents < 20.0, f"C4+noise detected {cents:.1f} cents off"


class TestSilence:
    """Silence must produce no voiced frames."""

    def test_silence_no_voiced_frames(self, tmp_path):
        wav = tmp_path / "silence.wav"
        write_silence_wav(duration=1.0, path=wav)
        result = track_pitch(wav)
        assert not result.voiced.any(), "Silence should produce 0 voiced frames"


class TestStereo:
    """Stereo input should be converted to mono without errors."""

    def test_stereo_converted_to_mono(self, tmp_path):
        sr = SAMPLE_RATE
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        mono = 0.8 * np.sin(2 * np.pi * midi_to_hz(60) * t)
        # Make stereo: left = signal, right = signal * 0.5
        stereo = np.column_stack([mono, mono * 0.5]).astype(np.float32)
        wav = tmp_path / "stereo_c4.wav"
        sf.write(str(wav), stereo, sr)

        result = track_pitch(wav)
        assert result.voiced.any()
        detected = median_voiced_freq(result)
        cents = abs(hz_to_cents_from_midi(detected, 60))
        assert cents < 20.0


def test_pitch_tracker_constants_cover_full_piano_range():
    assert FMIN_HZ == pytest.approx(27.50)  # A0
    assert FMAX_HZ == pytest.approx(4186.01, rel=1e-4)  # C8
