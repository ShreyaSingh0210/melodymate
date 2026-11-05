"""
core/segment.py
---------------
Turn per-frame pitch data into a list of discrete sung notes.

Algorithm:
  1. Smooth short glitches (1–2 anomalous frames) before segmenting.
  2. Walk frames; accumulate frames into the current note segment.
  3. Start a new segment when:
     - An unvoiced gap of >= UNVOICED_GAP_MS ms is found, or
     - The pitch deviates > PITCH_CHANGE_CENTS from the running median.
  4. Discard segments shorter than MIN_NOTE_MS ms.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from core.notes import freq_to_midi, midi_to_note_name, cents_off
from core.pitch import PitchResult

# ── Named constants (tune these to adjust segmentation behaviour) ──────────────

PITCH_CHANGE_CENTS: int = 70     # cents deviation triggers a new note
# The frame hop is about 23 ms. A single unvoiced frame can mark a deliberate
# tongue/glottal articulation between repeated notes, so split on one frame.
# This favors preserving repeated attacks; pYIN can still bridge very short
# gaps before segmentation, so extremely brief articulations may be invisible.
UNVOICED_GAP_MS: int = 20        # ms of detected silence that splits notes
MIN_NOTE_MS: int = 100           # discard notes shorter than this
GLITCH_FRAMES: int = 2           # smooth up to this many anomalous frames


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class SungNote:
    """One detected sung note."""
    midi_float: float    # median MIDI pitch (float, preserves microtonal detail)
    note_name: str       # nearest semitone name, e.g. "C4"
    cents_off: float     # signed cents from the nearest semitone
    start_time: float    # seconds
    end_time: float      # seconds


# ── Internal helpers ──────────────────────────────────────────────────────────

def _freq_to_midi_safe(freq: float) -> float:
    """Convert Hz to MIDI float; return NaN on invalid input."""
    try:
        return freq_to_midi(freq)
    except ValueError:
        return float("nan")


def _smooth_glitches(freqs: np.ndarray, voiced: np.ndarray, frame_times: np.ndarray) -> np.ndarray:
    """
    Replace short anomalous stretches (≤ GLITCH_FRAMES) with interpolated values.

    An anomalous frame is one where the MIDI pitch differs from its neighbours
    by more than PITCH_CHANGE_CENTS (handles octave jumps too).

    Returns a new frequency array with glitches smoothed.
    """
    smoothed = freqs.copy()
    n = len(freqs)

    i = 0
    while i < n:
        if not voiced[i]:
            i += 1
            continue

        # Look ahead for a short block of anomalous frames
        midi_here = _freq_to_midi_safe(smoothed[i])
        if math.isnan(midi_here):
            i += 1
            continue

        # Check whether the next GLITCH_FRAMES frames are outliers
        for glitch_len in range(1, GLITCH_FRAMES + 1):
            j = i + glitch_len
            if j >= n or not voiced[j]:
                break
            midi_next = _freq_to_midi_safe(smoothed[j])
            if math.isnan(midi_next):
                break
            if abs(midi_next - midi_here) * 100 > PITCH_CHANGE_CENTS:
                # Potential glitch block starts at j; check if it reconnects
                end = j + 1
                while end < n and end < j + GLITCH_FRAMES + 1 and voiced[end]:
                    midi_end = _freq_to_midi_safe(smoothed[end])
                    if not math.isnan(midi_end) and abs(midi_end - midi_here) * 100 <= PITCH_CHANGE_CENTS:
                        # Frames j..end-1 are a glitch; replace with midi_here's freq
                        for k in range(j, end):
                            smoothed[k] = freqs[i]  # use the stable pitch
                        break
                    end += 1
        i += 1

    return smoothed


def _build_segment(frame_freqs: list[float], start_time: float, end_time: float) -> SungNote | None:
    """
    Build a SungNote from a list of voiced frame frequencies.
    Returns None if the segment is shorter than MIN_NOTE_MS.
    """
    duration_ms = (end_time - start_time) * 1000.0
    if duration_ms < MIN_NOTE_MS:
        return None

    midis = np.array([_freq_to_midi_safe(f) for f in frame_freqs])
    midis = midis[~np.isnan(midis)]
    if len(midis) == 0:
        return None

    median_midi = float(np.median(midis))
    name = midi_to_note_name(median_midi)

    # cents_off expects a frequency; convert median midi back to Hz
    # Use 440 * 2**((midi - 69) / 12)
    median_hz = 440.0 * (2.0 ** ((median_midi - 69.0) / 12.0))
    c_off = cents_off(median_hz)

    return SungNote(
        midi_float=median_midi,
        note_name=name,
        cents_off=c_off,
        start_time=start_time,
        end_time=end_time,
    )


# ── Public function ────────────────────────────────────────────────────────────

def segment_notes(pitch_result: PitchResult) -> list[SungNote]:
    """
    Convert per-frame pitch data into a list of discrete sung notes.

    Parameters
    ----------
    pitch_result : PitchResult
        Output of core.pitch.track_pitch().

    Returns
    -------
    list[SungNote]
        Detected notes in time order.  Short notes (< MIN_NOTE_MS) are excluded.
    """
    times = pitch_result.times
    freqs = pitch_result.freqs
    voiced = pitch_result.voiced

    if len(times) == 0:
        return []

    # Step 1: smooth glitches
    freqs = _smooth_glitches(freqs, voiced, times)

    notes: list[SungNote] = []

    # Current segment accumulator
    seg_freqs: list[float] = []
    seg_start: float | None = None
    seg_midi_values: list[float] = []  # for running median of current segment

    # Frame duration (approximate, from hop size and sample rate)
    # We use time differences directly for gap detection
    n = len(times)
    articulation_indices: set[int] = set()
    if pitch_result.articulations is not None:
        articulation_indices = {
            int(np.searchsorted(times, float(event_time), side="left"))
            for event_time in pitch_result.articulations
            if float(event_time) > float(times[0])
        }

    for i in range(n):
        is_voiced = bool(voiced[i])
        t = float(times[i])
        freq = float(freqs[i])

        # Short acoustic attacks may be hidden by pYIN's overlapping windows.
        # Finish the prior note at the detected re-attack even if pitch is
        # unchanged and every pitch frame remains voiced.
        if i in articulation_indices and seg_start is not None:
            note = _build_segment(seg_freqs, seg_start, t)
            if note is not None:
                notes.append(note)
            seg_start = None
            seg_freqs = []
            seg_midi_values = []

        if is_voiced and not math.isnan(freq):
            midi_val = _freq_to_midi_safe(freq)
            if math.isnan(midi_val):
                # Treat as unvoiced
                is_voiced = False
            else:
                if seg_start is None:
                    # Starting a new segment
                    seg_start = t
                    seg_freqs = [freq]
                    seg_midi_values = [midi_val]
                else:
                    # Check if pitch deviates too far from current segment median
                    seg_median = float(np.median(seg_midi_values))
                    deviation_cents = abs(midi_val - seg_median) * 100.0

                    if deviation_cents > PITCH_CHANGE_CENTS:
                        # Finalise the current segment and start a new one
                        note = _build_segment(seg_freqs, seg_start, t)
                        if note is not None:
                            notes.append(note)
                        seg_start = t
                        seg_freqs = [freq]
                        seg_midi_values = [midi_val]
                    else:
                        seg_freqs.append(freq)
                        seg_midi_values.append(midi_val)
                continue

        # Unvoiced frame
        if seg_start is not None:
            # We're in a segment; check if the gap is long enough to split
            # Find how long the unvoiced run is by looking ahead
            gap_start_t = t
            j = i
            while j < n and (not voiced[j] or math.isnan(freqs[j])):
                j += 1

            gap_end_t = float(times[j]) if j < n else float(times[-1])
            gap_ms = (gap_end_t - gap_start_t) * 1000.0

            if gap_ms >= UNVOICED_GAP_MS:
                # Long enough gap: finalise segment
                note = _build_segment(seg_freqs, seg_start, gap_start_t)
                if note is not None:
                    notes.append(note)
                seg_start = None
                seg_freqs = []
                seg_midi_values = []
            # else: short gap, stay in current segment (glitch smoothing handles pitch)

    # Finalise any remaining segment at the end of the audio
    if seg_start is not None and seg_freqs:
        end_t = float(times[-1])
        note = _build_segment(seg_freqs, seg_start, end_t)
        if note is not None:
            notes.append(note)

    return notes
