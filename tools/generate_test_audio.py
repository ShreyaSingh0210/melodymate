"""
tools/generate_test_audio.py
----------------------------
Generates synthetic vocal test recordings with realistic singing phenomena:
1. test_c_major_up_scoops.wav: C major scale up with vocal attack scoops.
2. test_c_major_down_drift.wav: C major scale down with vibrato and pitch drift.
3. test_mary_lamb_legato.wav: Mary Had a Little Lamb in D major with legato repeated notes.
"""
from __future__ import annotations

import math
from pathlib import Path
import numpy as np
import soundfile as sf

AUDIO_DIR = Path(__file__).resolve().parent.parent / "tests" / "test_audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_RATE = 44100


def midi_to_hz(m: float) -> float:
    return 440.0 * (2.0 ** ((m - 69.0) / 12.0))


def generate_c_major_up_scoops(path: Path) -> None:
    """C major scale ascending with onset scoops on C4 and F4."""
    notes = [60, 62, 64, 65, 67, 69, 71, 72]
    sr = SAMPLE_RATE
    note_dur = 0.5
    gap_dur = 0.10
    total_samples = []

    for idx, midi in enumerate(notes):
        n_samples = int(note_dur * sr)
        t = np.arange(n_samples) / sr
        
        # Build instantaneous frequency
        freqs = np.full(n_samples, midi_to_hz(midi))
        if idx == 0:  # Scoop on the first note
            scoop_len = int(0.18 * sr)
            scoop_midis = np.linspace(midi + 1.2, midi, scoop_len)
            freqs[:scoop_len] = [midi_to_hz(m) for m in scoop_midis]
        elif idx == 3:  # Scoop on the fourth note
            scoop_len = int(0.14 * sr)
            scoop_midis = np.linspace(midi + 1.0, midi, scoop_len)
            freqs[:scoop_len] = [midi_to_hz(m) for m in scoop_midis]

        # Phase accumulation for variable frequency
        phase = 2.0 * np.pi * np.cumsum(freqs) / sr
        wave = np.sin(phase)

        # Smooth envelope
        fade_len = int(0.02 * sr)
        env = np.ones(n_samples)
        env[:fade_len] = np.linspace(0, 1, fade_len)
        env[-fade_len:] = np.linspace(1, 0, fade_len)
        wave = wave * env

        total_samples.append(wave)
        if idx < len(notes) - 1:
            total_samples.append(np.zeros(int(gap_dur * sr)))

    audio = np.concatenate(total_samples) * 0.75
    sf.write(str(path), audio, sr, subtype="PCM_16")


def generate_c_major_down_drift(path: Path) -> None:
    """C major scale descending with natural 5 Hz vibrato and slight downward pitch drift."""
    notes = [72, 71, 69, 67, 65, 64, 62, 60]
    sr = SAMPLE_RATE
    note_dur = 0.48
    gap_dur = 0.09
    total_samples = []

    for idx, midi in enumerate(notes):
        n_samples = int(note_dur * sr)
        t = np.arange(n_samples) / sr

        # Drift increases across the scale (up to -30 cents flat by the end)
        drift_cents = - (idx / len(notes)) * 28.0
        # Vibrato: 5 Hz, amplitude 20 cents
        vibrato_cents = 20.0 * np.sin(2.0 * np.pi * 5.0 * t)
        inst_midi = midi + (drift_cents + vibrato_cents) / 100.0

        freqs = np.array([midi_to_hz(m) for m in inst_midi])
        phase = 2.0 * np.pi * np.cumsum(freqs) / sr
        wave = np.sin(phase)

        fade_len = int(0.02 * sr)
        env = np.ones(n_samples)
        env[:fade_len] = np.linspace(0, 1, fade_len)
        env[-fade_len:] = np.linspace(1, 0, fade_len)
        wave = wave * env

        total_samples.append(wave)
        if idx < len(notes) - 1:
            total_samples.append(np.zeros(int(gap_dur * sr)))

    audio = np.concatenate(total_samples) * 0.75
    sf.write(str(path), audio, sr, subtype="PCM_16")


def generate_mary_lamb_legato(path: Path) -> None:
    """
    Mary Had a Little Lamb in D major (shift +2).
    Repeated notes have continuous voicing (0 gap) but an amplitude valley of ~10 dB.
    """
    # Transposed +2 semitones from C to D
    notes = [
        66, 64, 62, 64, 66, 66, 66,
        64, 64, 64, 66, 69, 69,
        66, 64, 62, 64, 66, 66, 66,
        64, 64, 66, 64, 62,
    ]
    sr = SAMPLE_RATE
    note_dur = 0.42
    total_samples = []

    for idx, midi in enumerate(notes):
        n_samples = int(note_dur * sr)
        t = np.arange(n_samples) / sr
        freq = midi_to_hz(midi)
        wave = np.sin(2.0 * np.pi * freq * t)

        is_repeated_next = (idx < len(notes) - 1 and notes[idx + 1] == midi)

        if is_repeated_next:
            # Legato: no silence gap, but energy dips down by 75% (-12 dB) at the end
            dip_len = int(0.08 * sr)
            env = np.ones(n_samples)
            fade_in = int(0.02 * sr)
            env[:fade_in] = np.linspace(0.4, 1.0, fade_in)
            env[-dip_len:] = np.linspace(1.0, 0.25, dip_len)
            wave = wave * env
            total_samples.append(wave)
            # No silence gap appended! Continuous voicing into next note.
        else:
            # Normal transition: fade out and short 70 ms gap
            fade_len = int(0.02 * sr)
            env = np.ones(n_samples)
            env[:fade_len] = np.linspace(0, 1, fade_len)
            env[-fade_len:] = np.linspace(1, 0, fade_len)
            wave = wave * env
            total_samples.append(wave)
            if idx < len(notes) - 1:
                total_samples.append(np.zeros(int(0.07 * sr)))

    audio = np.concatenate(total_samples) * 0.75
    sf.write(str(path), audio, sr, subtype="PCM_16")


def main():
    print("Generating test audio files in:", AUDIO_DIR)
    f1 = AUDIO_DIR / "test_c_major_up_scoops.wav"
    f2 = AUDIO_DIR / "test_c_major_down_drift.wav"
    f3 = AUDIO_DIR / "test_mary_lamb_legato.wav"

    generate_c_major_up_scoops(f1)
    print("Generated:", f1.name)
    generate_c_major_down_drift(f2)
    print("Generated:", f2.name)
    generate_mary_lamb_legato(f3)
    print("Generated:", f3.name)


if __name__ == "__main__":
    main()
