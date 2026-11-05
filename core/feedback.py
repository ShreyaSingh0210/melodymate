"""
core/feedback.py
----------------
Turns a list of NoteResult objects into plain English sentences.

Rules:
- No emoji or symbols.
- Note names spelled out for screen readers: "C sharp 4", not "C#4".
- Use "higher" / "lower" instead of "sharp" / "flat".
- First sentence is always the score.
- Under ~45 words for short melodies (five notes or fewer).
- If nothing was detected, give a device-specific hint.
- For melodies over 8 notes, list at most 3 problems then say "and N more".
- In relative mode, report how far the singer was from the written key.
"""

from __future__ import annotations

from core.melody import NoteResult
from core.notes import midi_to_note_name


# ── Helpers ────────────────────────────────────────────────────────────────────

def _spell_note_name(midi: float) -> str:
    """
    Return a screen-reader-friendly note name, e.g. "C sharp 4".

    Converts "C#4" → "C sharp 4", "F#3" → "F sharp 3", "C4" → "C 4".
    """
    raw = midi_to_note_name(midi)   # e.g. "C#4" or "C4"

    if "#" in raw:
        pitch, octave = raw.split("#")
        return f"{pitch} sharp {octave}"
    else:
        # Separate letter(s) from octave number for readability
        # raw is like "C4" or "A0"; find where digits start
        for i, ch in enumerate(raw):
            if ch == "-" or ch.isdigit():
                break
        pitch = raw[:i]
        octave = raw[i:]
        return f"{pitch} {octave}"


def _ordinal(n: int) -> str:
    """Return "1st", "2nd", "3rd", "4th", etc."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


# ── Public function ────────────────────────────────────────────────────────────

def generate_feedback(
    results: list[NoteResult],
    input_type: str = "keyboard",
    shift_used: int = 0,
) -> str:
    """
    Generate plain English feedback from a list of NoteResult objects.

    Parameters
    ----------
    results : list[NoteResult]
        Output of core.melody.compare().
    input_type : str
        "keyboard" or "singing" — affects wording and empty-detection hints.
    shift_used : int
        The semitone shift that was applied in relative mode
        (CompareResults.shift_used).  0 means no shift / non-relative mode.
        When non-zero, an extra sentence is added after the score that
        describes how far the singer was from the written key.

    Returns
    -------
    str
        One or more sentences of feedback suitable for a screen reader.
    """
    verb = "played" if input_type == "keyboard" else "sang"

    # ── Handle empty performance ───────────────────────────────────────────────
    if not results or all(r.label == "missing" for r in results):
        if input_type == "singing":
            return (
                "Nothing was detected. "
                "Please check that your microphone is connected and try singing louder."
            )
        else:
            return (
                "Nothing was detected. "
                "Please check that your MIDI keyboard is connected. "
                "You can verify it in Windows Device Manager under Sound, video and game controllers."
            )

    # ── Count reference notes and correct notes ────────────────────────────────
    ref_notes = [r for r in results if r.label != "extra"]
    total = len(ref_notes)
    correct = sum(1 for r in ref_notes if r.label == "correct")

    sentences: list[str] = []

    # First sentence: always the score
    sentences.append(f"You {verb} {correct} of {total} notes correctly.")

    # ── Relative-mode key-offset sentence ─────────────────────────────────────
    if shift_used != 0:
        abs_shift = abs(shift_used)
        direction = "higher" if shift_used < 0 else "lower"
        # shift_used is how much we added to the performance to match reference.
        # A positive shift_used means we shifted performance UP, i.e. they sang lower.
        # A negative shift_used means we shifted performance DOWN, i.e. they sang higher.
        semitone_word = "semitone" if abs_shift == 1 else "semitones"
        sentences.append(
            f"You sang about {abs_shift} {semitone_word} {direction} than the written key."
        )

    # ── Per-error sentences ────────────────────────────────────────────────────
    # For long melodies (more than 8 reference notes), cap problem sentences at 3.
    long_melody = total > 8
    problem_sentences: list[str] = []
    problem_count = 0

    for result in results:
        if long_melody and problem_count >= 3:
            break  # "and N more" is added after the loop

        if result.label == "wrong":
            problem_count += 1
            if input_type == "singing" and result.cents_error is not None:
                cents = round(result.cents_error)
                direction_c = "higher" if cents > 0 else "lower"
                expected_name = _spell_note_name(result.ref_midi)
                problem_sentences.append(
                    f"Note {result.position}, {expected_name}, was about {abs(cents)} cents {direction_c}."
                )
            else:
                played_name = _spell_note_name(result.perf_midi)
                expected_name = _spell_note_name(result.ref_midi)
                problem_sentences.append(
                    f"Note {result.position} was {played_name}, expected {expected_name}."
                )

        elif result.label == "missing":
            problem_count += 1
            ref_name = _spell_note_name(result.ref_midi)
            problem_sentences.append(f"You missed note {result.position}, {ref_name}.")

        elif result.label == "extra":
            problem_count += 1
            played_name = _spell_note_name(result.perf_midi)
            if result.position == 0:
                problem_sentences.append(
                    f"You {verb} an extra note, {played_name}, at the start."
                )
            else:
                problem_sentences.append(
                    f"You {verb} an extra note, {played_name}, after position {result.position}."
                )

    sentences.extend(problem_sentences)

    # Count total problems (not just the 3 shown)
    if long_melody:
        total_problems = sum(
            1 for r in results if r.label in ("wrong", "missing", "extra")
        )
        remaining = total_problems - len(problem_sentences)
        if remaining > 0:
            sentences.append(f"And {remaining} more.")

    return " ".join(sentences)

