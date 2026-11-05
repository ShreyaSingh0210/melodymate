"""
core/pitch.py
-------------
Pitch tracking from a WAV file using librosa's pYIN algorithm.

pYIN is a probabilistic variant of YIN and is well-suited to singing.
It returns per-frame pitch estimates and voiced/unvoiced flags.

Post-processing: frames where the audio RMS energy is more than
SILENCE_THRESHOLD_DB below the loudest frame are forced to unvoiced.
This prevents pYIN from bridging silent gaps between identical pitches.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
import librosa

# ── Named constants ────────────────────────────────────────────────────────────

# Full standard 88-key piano range: A0 (MIDI 21) through C8 (MIDI 108).
# These are the fundamental frequencies at equal temperament, A4 = 440 Hz.
FMIN_HZ: float = 27.50       # A0
FMAX_HZ: float = 4186.01    # C8

# Frames whose RMS energy is more than this many dB below the loudest frame
# are forced to unvoiced, regardless of what pYIN reports.
# This catches silent gaps that pYIN would otherwise bridge.
SILENCE_THRESHOLD_DB: float = 40.0


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class PitchResult:
    """Per-frame pitch tracking output from pYIN."""
    times: np.ndarray    # shape (N,) — time of each frame in seconds
    freqs: np.ndarray    # shape (N,) — Hz; NaN where unvoiced
    voiced: np.ndarray   # shape (N,) — bool; True where a pitch was detected
    articulations: np.ndarray | None = None  # note re-attacks detected from short energy dips


def _correct_octave_errors(
    audio: np.ndarray, sr: int, times: np.ndarray, freqs: np.ndarray,
    voiced: np.ndarray, frame_length: int,
) -> np.ndarray:
    """Use local spectrum evidence to reject strong octave harmonics.

    pYIN normally handles harmonic-rich voices well, but it can occasionally
    select a strong octave harmonic or a low subharmonic. Propose octave
    changes only when the corresponding spectral bin has clear support, then
    require the same proposal in neighboring frames to avoid reacting to
    brief pitch transitions.
    """
    proposed = np.zeros(len(freqs), dtype=np.int8)  # -1 down, +1 up
    half = frame_length // 2
    window = np.hanning(frame_length)

    def local_magnitude(spectrum: np.ndarray, hz: float) -> float:
        bin_index = int(round(hz * frame_length / sr))
        if bin_index <= 0 or bin_index >= len(spectrum):
            return 0.0
        return float(np.max(spectrum[max(0, bin_index - 1):min(len(spectrum), bin_index + 2)]))

    for i in np.flatnonzero(voiced & np.isfinite(freqs)):
        hz = float(freqs[i])
        center = int(round(float(times[i]) * sr))
        start = center - half
        frame = np.zeros(frame_length, dtype=np.float64)
        src_start, src_end = max(0, start), min(len(audio), start + frame_length)
        if src_end <= src_start:
            continue
        frame[src_start - start:src_end - start] = audio[src_start:src_end]
        spectrum = np.abs(np.fft.rfft(frame * window))
        here = local_magnitude(spectrum, hz)
        if here <= 1e-8:
            continue

        if hz / 2 >= FMIN_HZ:
            subharmonic = local_magnitude(spectrum, hz / 2)
            if subharmonic >= here * 0.10:
                proposed[i] = -1
        if hz * 2 <= FMAX_HZ:
            octave = local_magnitude(spectrum, hz * 2)
            if octave >= here * 12.5:
                proposed[i] = 1

    corrected = freqs.copy()
    for i, direction in enumerate(proposed):
        if direction == 0:
            continue
        left, right = max(0, i - 2), min(len(proposed), i + 3)
        if np.count_nonzero(proposed[left:right] == direction) >= 3:
            corrected[i] *= 0.5 if direction < 0 else 2.0
    return corrected


# ── Public function ────────────────────────────────────────────────────────────

def track_pitch(wav_path: str | Path) -> PitchResult:
    """
    Load a WAV file and run pYIN pitch tracking on it.

    Stereo files are converted to mono by averaging channels.
    Returns per-frame times, frequencies (Hz), and voiced flags.

    Parameters
    ----------
    wav_path : str or Path
        Path to a WAV file.  Must be readable by soundfile.

    Returns
    -------
    PitchResult
        times  : seconds per frame (float64 array)
        freqs  : Hz per frame; NaN where no pitch detected (float64 array)
        voiced : bool per frame (bool array)
    """
    wav_path = Path(wav_path)

    # Load audio with soundfile (preserves original sample rate)
    audio, sr = sf.read(str(wav_path), dtype="float32", always_2d=True)

    # Convert stereo (or more channels) to mono by averaging
    if audio.ndim == 2 and audio.shape[1] > 1:
        audio = audio.mean(axis=1)
    else:
        audio = audio[:, 0]

    # librosa.pyin returns three arrays:
    #   f0          — fundamental frequency per frame (NaN where unvoiced)
    #   voiced_flag — bool array
    #   voiced_prob — probability of voicing (we don't use this)
    # Resample to 22.05 kHz. This comfortably covers C8 (4.19 kHz), while
    # keeping the A0 period short enough for a practical analysis window.
    analysis_sr = 22050
    if sr != analysis_sr:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=analysis_sr)
    sr = analysis_sr

    # Four periods of A0 fit within the analysis window; the 512-sample hop
    # still gives pitch updates about every 23 ms.
    hop_length = 512
    frame_length = 4096

    f0, voiced_flag, _voiced_prob = librosa.pyin(
        audio,
        fmin=FMIN_HZ,
        fmax=FMAX_HZ,
        sr=sr,
        frame_length=frame_length,
        hop_length=hop_length,
    )

    # Build time axis matching the frames pyin produced
    n_frames = len(f0)
    times = librosa.frames_to_time(np.arange(n_frames), sr=sr, hop_length=hop_length)

    # ── Energy-based silence correction ───────────────────────────────────────
    # Compute the RMS energy of each frame and force unvoiced where it is
    # SILENCE_THRESHOLD_DB below the loudest frame.
    # This prevents pYIN from bridging silent gaps between identical pitches.
    rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]

    # Align rms length to f0 length (librosa may differ by 1 frame)
    min_len = min(len(rms), n_frames)
    rms = rms[:min_len]
    f0_out = f0[:min_len].astype(np.float64)
    voiced_out = voiced_flag[:min_len].astype(bool)
    times_out = times[:min_len].astype(np.float64)
    f0_out = _correct_octave_errors(audio, sr, times_out, f0_out, voiced_out, frame_length)

    # Convert to dB relative to the peak frame; silence frames have very low dB.
    peak_rms = rms.max()
    if peak_rms > 0:
        # Add a small epsilon to avoid log(0)
        rms_db = 20.0 * np.log10(rms / peak_rms + 1e-10)
        silent_frames = rms_db < -SILENCE_THRESHOLD_DB
        # Force silent frames to unvoiced and set their frequency to NaN
        voiced_out[silent_frames] = False
        f0_out[silent_frames] = np.nan

    # pYIN's long window can carry a pitch estimate across a brief stop in
    # singing. Find short, near-silent gaps with a 10 ms window and 5 ms hop;
    # the segmenter uses the end of each gap as a re-attack boundary. Local
    # normalization avoids treating a naturally quiet recording as silence.
    short_frame = max(128, int(round(sr * 0.010)))
    short_hop = max(64, short_frame // 2)
    short_rms = librosa.feature.rms(
        y=audio, frame_length=short_frame, hop_length=short_hop
    )[0]
    short_times = librosa.frames_to_time(
        np.arange(len(short_rms)), sr=sr, hop_length=short_hop
    )
    radius = max(1, int(round(0.10 * sr / short_hop)))
    local_peaks = np.array([
        short_rms[max(0, i - radius):min(len(short_rms), i + radius + 1)].max()
        for i in range(len(short_rms))
    ])
    low_energy = (short_rms < np.maximum(local_peaks * 0.08, 1e-5)) & (local_peaks > 1e-4)
    articulations: list[float] = []
    i = 0
    while i < len(low_energy):
        if not low_energy[i]:
            i += 1
            continue
        start = i
        while i < len(low_energy) and low_energy[i]:
            i += 1
        end = i
        gap_seconds = (end - start) * short_hop / sr
        if start > 0 and end < len(low_energy) and 0.005 <= gap_seconds <= 0.35:
            # The first post-gap frame is a better estimate of the new attack
            # than the midpoint, and is quantized to the pitch-frame grid.
            attack_time = float(short_times[end])
            frame_index = int(np.searchsorted(times_out, attack_time, side="left"))
            if frame_index < len(times_out):
                articulations.append(float(times_out[frame_index]))

    return PitchResult(
        times=times_out,
        freqs=f0_out,
        voiced=voiced_out,
        articulations=np.asarray(articulations, dtype=np.float64),
    )
