"""
core/notes.py
-------------
Conversions between frequencies (Hz), MIDI numbers, and note names.

MIDI numbering: A4 = 69, C4 = 60.
All sharps (no flats): C, C#, D, D#, E, F, F#, G, G#, A, A#, B.
"""

import math

# ── Constants ─────────────────────────────────────────────────────────────────

A4_MIDI: int = 69
A4_HZ: float = 440.0

# Standard 88-key piano range (A0 through C8).
PIANO_MIN_MIDI: int = 21
PIANO_MAX_MIDI: int = 108

# 12 pitch-class names, index = semitone within octave (0 = C)
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_FLAT_ALIASES = {"DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validate_freq(freq: float) -> None:
    """Raise ValueError for zero, negative, or NaN frequencies."""
    # math.isnan returns False for non-floats, so convert first
    if isinstance(freq, float) and math.isnan(freq):
        raise ValueError(f"Frequency must be a positive number, got NaN.")
    if freq <= 0:
        raise ValueError(f"Frequency must be positive, got {freq}.")


# ── Public functions ───────────────────────────────────────────────────────────

def freq_to_midi(freq: float) -> float:
    """
    Convert a frequency in Hz to a MIDI number (float).

    Uses the standard formula: midi = 69 + 12 * log2(freq / 440).
    Returns a float so callers can see how far off a semitone the pitch is.

    Raises ValueError for zero, negative, or NaN input.
    """
    _validate_freq(freq)
    return A4_MIDI + 12.0 * math.log2(freq / A4_HZ)


def midi_to_note_name(midi: float) -> str:
    """
    Convert a MIDI number to a note name like "C4" or "F#3".

    Rounds to the nearest semitone first, so it works on the float
    values that freq_to_midi returns.
    """
    midi_int = round(midi)
    # Octave: MIDI 0-11 is octave -1, 12-23 is octave 0, etc.
    octave = (midi_int // 12) - 1
    pitch_class = midi_int % 12
    return f"{_NOTE_NAMES[pitch_class]}{octave}"


def note_name_to_midi(name: str) -> int:
    """
    Convert a note name like "C4" or "F#3" to an integer MIDI number.

    Supports sharps only (e.g. "C#4"), not flats.
    Raises ValueError for unrecognised names.
    """
    name = name.strip()

    # Split into pitch class ("C", "C#", ...) and octave number
    if len(name) >= 2 and name[1] in "#bB":
        pitch_str = name[:2]   # e.g. "C#" or "Bb"
        octave_str = name[2:]  # e.g. "4"
    else:
        pitch_str = name[:1]   # e.g. "C"
        octave_str = name[1:]  # e.g. "4"

    # Accept common flat spellings as aliases for their enharmonic sharps.
    pitch_str = _FLAT_ALIASES.get(pitch_str.upper(), pitch_str)
    if pitch_str not in _NOTE_NAMES:
        raise ValueError(f"Unknown pitch class: '{pitch_str}' in '{name}'.")

    try:
        octave = int(octave_str)
    except ValueError:
        raise ValueError(f"Cannot parse octave from '{name}'.")

    pitch_class = _NOTE_NAMES.index(pitch_str)
    # Inverse of midi_to_note_name: octave -1 starts at MIDI 0
    return (octave + 1) * 12 + pitch_class


def cents_off(freq: float) -> float:
    """
    Return how many cents the frequency is from the nearest semitone.

    Negative  → frequency is below the nearest note (flat).
    Positive  → frequency is above the nearest note (sharp).
    Range: (-50, +50].

    Raises ValueError for zero, negative, or NaN input.
    """
    _validate_freq(freq)
    midi_exact = freq_to_midi(freq)
    midi_rounded = round(midi_exact)
    # Each semitone = 100 cents
    return (midi_exact - midi_rounded) * 100.0


def piano_key_numbers() -> list[int]:
    """Return MIDI numbers for all 88 standard piano keys, from A0 to C8."""
    return list(range(PIANO_MIN_MIDI, PIANO_MAX_MIDI + 1))


def piano_key_names() -> list[str]:
    """Return the note names for all 88 standard piano keys, from A0 to C8."""
    return [midi_to_note_name(midi) for midi in piano_key_numbers()]
