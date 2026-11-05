"""
core/synth.py
-------------
Write reference melody audio to a WAV file as sine tones.

This module never plays audio itself.  It only writes files.
Callers (tools/analyze_wav.py, tests) read those files back.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

# ── Default parameters ────────────────────────────────────────────────────────

SAMPLE_RATE: int = 44100          # Hz
NOTE_DURATION: float = 0.5        # seconds per note
FADE_MS: float = 10.0             # fade-in and fade-out duration in milliseconds
SILENCE_MS: float = 120.0        # silence gap between notes in milliseconds (≥ 120 ms so
                                  # repeated notes are never merged by the segmenter)


# ── Public function ────────────────────────────────────────────────────────────

def write_melody_wav(
    midi_numbers: list[int],
    output_path: str | Path,
    note_duration: float = NOTE_DURATION,
    sample_rate: int = SAMPLE_RATE,
    silence_ms: float = SILENCE_MS,
    note_durations: list[float] | None = None,
) -> None:
    """
    Render a list of MIDI numbers as sine tones and save to a WAV file.

    Each note is a pure sine wave of the corresponding frequency.  A short
    fade-in and fade-out (FADE_MS ms each) prevents clicks at note boundaries.
    Between every pair of adjacent notes a silence gap of *silence_ms*
    milliseconds (default 120 ms) is inserted so that repeated notes are not
    accidentally merged by the pitch segmenter.

    Parameters
    ----------
    midi_numbers : list[int]
        MIDI note numbers to render, in order.
    output_path : str or Path
        Destination WAV file path.  Overwritten if it already exists.
    note_duration : float
        Duration of each note in seconds (default 0.5 s).
    sample_rate : int
        Sample rate of the output WAV (default 44 100 Hz).
    silence_ms : float
        Duration of the inter-note silence gap in milliseconds (default 120 ms).
        Must be >= 120 ms to keep repeated notes separate through segmentation.
    note_durations : list[float] or None
        Optional per-note durations in seconds. When provided, it must contain
        one positive duration for every MIDI note.
    """
    output_path = Path(output_path)
    n_silence = int((silence_ms / 1000.0) * sample_rate)
    if note_durations is not None and len(note_durations) != len(midi_numbers):
        raise ValueError("note_durations must contain one duration per MIDI note")

    # Silence block inserted between notes
    gap = np.zeros(n_silence)

    all_samples = []

    for idx, midi in enumerate(midi_numbers):
        duration = note_duration if note_durations is None else note_durations[idx]
        if duration <= 0:
            raise ValueError("note durations must be positive")
        n_samples_per_note = int(duration * sample_rate)
        fade_samples = min(int((FADE_MS / 1000.0) * sample_rate), n_samples_per_note // 2)
        fade_in = np.linspace(0.0, 1.0, fade_samples)
        fade_out = np.linspace(1.0, 0.0, fade_samples)
        t = np.arange(n_samples_per_note) / sample_rate

        # Convert MIDI number to frequency: f = 440 * 2^((midi - 69) / 12)
        freq_hz = 440.0 * (2.0 ** ((midi - 69.0) / 12.0))

        # Generate sine wave at unit amplitude
        tone = np.sin(2.0 * np.pi * freq_hz * t)

        # Apply fade-in and fade-out to avoid clicks
        tone[:fade_samples] *= fade_in
        tone[-fade_samples:] *= fade_out

        all_samples.append(tone)

        # Add silence after every note except the last
        if idx < len(midi_numbers) - 1:
            all_samples.append(gap)

    # Concatenate all notes (and gaps) into one array and scale to a comfortable level
    audio = np.concatenate(all_samples) * 0.8   # 0.8 keeps headroom

    sf.write(str(output_path), audio, sample_rate, subtype="PCM_16")
