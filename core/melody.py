"""
core/melody.py
--------------
Reference melodies and sequence comparison via edit-distance alignment.

Works on plain lists of MIDI numbers (ints or floats for singing).
Knows nothing about MIDI hardware or audio files.

Relative mode
~~~~~~~~~~~~~
Instead of naively aligning the first performed note to the first reference
note (which breaks when the first detected note is a glitch), relative mode
tries every whole-semitone shift from -12 to +12, runs the normal alignment
for each, and keeps the shift that produces the most correct notes.  Ties are
broken by choosing the shift with the smallest absolute value (i.e. closest to
no transposition).  The winning shift is stored in CompareResults.shift_used.
"""

from __future__ import annotations
from dataclasses import dataclass

from core.notes import midi_to_note_name

# ── Named constant ─────────────────────────────────────────────────────────────

# A performed note counts as "correct" if it is within this many cents of the
# reference note.  MIDI keyboard notes always have 0 cents error.
CENTS_THRESHOLD: int = 50


# ── Reference melodies ─────────────────────────────────────────────────────────
# Stored as lists of integer MIDI numbers.

MELODIES: dict[str, list[int]] = {
    "c_major_up": [60, 62, 64, 65, 67, 69, 71, 72],
    "c_major_down": [72, 71, 69, 67, 65, 64, 62, 60],
    "mary_lamb": [
        64, 62, 60, 62, 64, 64, 64,
        62, 62, 62, 64, 67, 67,
        64, 62, 60, 62, 64, 64, 64,
        62, 62, 64, 62, 60,
    ],
}

# Expected note lengths in quarter-note beats. Timing feedback adapts to the
# singer's overall tempo, while these ratios preserve the written rhythm.
MELODY_BEATS: dict[str, list[float]] = {
    "c_major_up": [1.0] * 8,
    "c_major_down": [1.0] * 8,
    # Mary Had a Little Lamb: longer phrase-ending notes are two beats.
    "mary_lamb": [
        1, 1, 1, 1, 1, 1, 2,
        1, 1, 2, 1, 1, 2,
        1, 1, 1, 1, 1, 1, 2,
        1, 1, 1, 1, 2,
    ],
}


# ── Result container ──────────────────────────────────────────────────────────

class CompareResults(list):
    """
    A plain Python list of NoteResult objects with one extra attribute:

    shift_used : int
        The semitone shift applied to the performance before alignment.
        Always 0 in "exact" and "ignore_octave" modes.
        In "relative" mode this is the shift that produced the best alignment.
    """

    def __init__(self, iterable=(), *, shift_used: int = 0):
        super().__init__(iterable)
        self.shift_used: int = shift_used

# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class NoteResult:
    """Alignment result for one reference or performed note."""
    label: str             # "correct" | "wrong" | "missing" | "extra"
    ref_midi: int | None   # Reference MIDI number (None for extra notes)
    perf_midi: float | None  # Performed MIDI number; float allows sung pitch
    cents_error: float | None  # Signed cents; None means not applicable
    position: int          # 1-based index into the reference sequence


# ── Internal: edit-distance alignment ─────────────────────────────────────────

def _align(reference: list[int], performed: list[float]) -> list[tuple[int | None, float | None]]:
    """
    Align two sequences using Wagner-Fischer edit distance.

    Returns a list of (ref_note, perf_note) pairs where:
      - (ref, perf) → substitution or match
      - (ref, None) → ref note was missing from performance
      - (None, perf) → extra note in performance

    Cost model: match=0, substitution=1, insertion=1, deletion=1.
    Comparison is by semitone (round to nearest int) so sung notes align
    to the closest reference pitch.
    """
    n = len(reference)
    m = len(performed)

    # Build the cost table.  dp[i][j] = min edits to align ref[:i] with perf[:j].
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i   # delete all ref notes
    for j in range(m + 1):
        dp[0][j] = j   # insert all perf notes

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            # Compare by nearest semitone
            match = round(reference[i - 1]) == round(performed[j - 1])
            if match:
                dp[i][j] = dp[i - 1][j - 1]          # free match
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j - 1],  # substitution
                    dp[i - 1][j],      # delete ref note (missing)
                    dp[i][j - 1],      # insert perf note (extra)
                )

    # Traceback from dp[n][m] to recover the alignment.
    alignment: list[tuple[int | None, float | None]] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            match = round(reference[i - 1]) == round(performed[j - 1])
            if match and dp[i][j] == dp[i - 1][j - 1]:
                alignment.append((reference[i - 1], performed[j - 1]))
                i -= 1
                j -= 1
                continue
            if dp[i][j] == 1 + dp[i - 1][j - 1]:
                # substitution
                alignment.append((reference[i - 1], performed[j - 1]))
                i -= 1
                j -= 1
                continue
        if i > 0 and dp[i][j] == 1 + dp[i - 1][j]:
            # missing (deletion of ref)
            alignment.append((reference[i - 1], None))
            i -= 1
        else:
            # extra (insertion of perf)
            alignment.append((None, performed[j - 1]))
            j -= 1

    alignment.reverse()
    return alignment


# ── Public comparison function ─────────────────────────────────────────────────

def compare(
    reference: list[int],
    performed: list[float],
    mode: str = "exact",
) -> "CompareResults":
    """
    Compare a performed note sequence against a reference.

    Parameters
    ----------
    reference : list[int]
        MIDI numbers from the reference melody.
    performed : list[float]
        MIDI numbers from the performance.  Use floats for sung notes so the
        unrounded pitch is preserved for cents reporting.  MIDI keyboard notes
        can be plain ints (treated as exact, 0 cents error).
    mode : str
        "exact"         – compare notes as-is.
        "ignore_octave" – compare pitch classes (midi % 12) only.
        "relative"      – try every whole-semitone shift from -12 to +12,
                          run the normal alignment for each, and keep the
                          shift with the most correct notes (tie-break:
                          smallest absolute shift).  The winning shift is
                          recorded in CompareResults.shift_used.
                          If performance is empty, all reference notes are
                          missing and shift_used is 0.

    Returns
    -------
    CompareResults
        A list subclass of NoteResult objects with an extra .shift_used
        attribute (always 0 except in relative mode).
        Extra notes append beyond reference length.
    """
    if not reference:
        return CompareResults(shift_used=0)

    # ── Relative mode: brute-force best shift ──────────────────────────────────
    if mode == "relative":
        if not performed:
            # Empty performance → all missing
            missing = [
                NoteResult(
                    label="missing",
                    ref_midi=r,
                    perf_midi=None,
                    cents_error=None,
                    position=i + 1,
                )
                for i, r in enumerate(reference)
            ]
            return CompareResults(missing, shift_used=0)

        best_results: list[NoteResult] = []
        best_correct = -1
        best_shift = 0

        for shift in range(-12, 13):   # -12 … +12 inclusive
            perf_shifted = [p + shift for p in performed]
            candidate = _build_results(reference, performed, perf_shifted, mode="relative")
            correct = sum(1 for r in candidate if r.label == "correct")
            # Better if more correct, or equal correct with a smaller |shift|
            if correct > best_correct or (
                correct == best_correct and abs(shift) < abs(best_shift)
            ):
                best_correct = correct
                best_shift = shift
                best_results = candidate

        return CompareResults(best_results, shift_used=best_shift)

    # Apply mode transforms to working copies (exact / ignore_octave)
    ref_work = list(reference)
    perf_work = list(performed)

    if mode == "ignore_octave":
        ref_work = [r % 12 for r in ref_work]
        perf_work = [p % 12 for p in perf_work]

    # Run alignment on (possibly transformed) sequences (exact / ignore_octave).
    results = _build_results(reference, performed, perf_work, mode=mode)
    return CompareResults(results, shift_used=0)


# ── Internal: build NoteResult list from aligned sequences ────────────────────

def _build_results(
    reference: list[int],
    performed: list[float],
    perf_work: list[float],
    mode: str,
) -> list[NoteResult]:
    """
    Align *perf_work* against *reference* and map results back to original
    (untransformed) pitches from *performed*.  *mode* is used only to choose
    the correct cents-error formula.

    For relative mode, *perf_work* is the already-shifted performance and
    *reference* is used as-is (no further transformation).
    """
    ref_work = list(reference)

    if mode == "ignore_octave":
        ref_work = [r % 12 for r in ref_work]
        # perf_work is already transformed by the caller in ignore_octave path;
        # for relative mode the caller passes shifted floats, no % 12 needed.

    alignment = _align(ref_work, perf_work)

    results: list[NoteResult] = []
    ref_position = 0    # tracks 1-based position in the original reference
    ref_idx = 0
    perf_idx = 0

    for (r_aligned, p_aligned) in alignment:
        if r_aligned is not None and p_aligned is not None:
            # Match or substitution — advance both indices
            ref_position += 1
            orig_ref = reference[ref_idx]
            orig_perf = performed[perf_idx]
            ref_idx += 1
            perf_idx += 1

            # Correctness is judged on the TRANSFORMED values so that
            # ignore_octave and relative modes work correctly.
            # For ignore_octave, use circular pitch-class distance so that
            # adjacent pitch classes (e.g. B=11 and C=0) are 1 semitone apart,
            # not 11 semitones apart.
            if mode == "ignore_octave":
                d = abs(p_aligned - r_aligned) % 12
                cents_err = min(d, 12 - d) * 100.0
                # Preserve sign: positive if performed is "higher" on the circle
                raw_diff = (p_aligned - r_aligned) % 12
                if raw_diff > 6:
                    cents_err = -cents_err
            else:
                # For both exact and relative mode, p_aligned is the
                # (possibly shifted) performed pitch; r_aligned is the
                # reference pitch.  The difference gives the tuning error
                # relative to the reference (shift already baked in for
                # relative mode).
                cents_err = (p_aligned - r_aligned) * 100.0

            if abs(cents_err) <= CENTS_THRESHOLD:
                label = "correct"
            else:
                label = "wrong"

            # For display we report original (untransformed) pitches, but the
            # cents_error field uses the transformed comparison so the number
            # makes sense to the user (e.g. in relative mode the shift is
            # already baked in, so 0 cents means "in tune relative to ref").
            results.append(NoteResult(
                label=label,
                ref_midi=orig_ref,
                perf_midi=orig_perf,
                cents_error=cents_err,
                position=ref_position,
            ))

        elif r_aligned is not None and p_aligned is None:
            # Missing note
            ref_position += 1
            orig_ref = reference[ref_idx]
            ref_idx += 1
            results.append(NoteResult(
                label="missing",
                ref_midi=orig_ref,
                perf_midi=None,
                cents_error=None,
                position=ref_position,
            ))

        else:
            # Extra note (p_aligned is not None, r_aligned is None)
            orig_perf = performed[perf_idx]
            perf_idx += 1
            results.append(NoteResult(
                label="extra",
                ref_midi=None,
                perf_midi=orig_perf,
                cents_error=None,
                position=ref_position,  # position within ref where it appeared
            ))

    # TODO(rhythm): Add duration comparison here.
    # When rhythm data is available, each NoteResult will gain a duration_error_ms
    # field, and this function can compare performed vs. reference durations.
    # The label may change from "correct" to "correct_pitch_wrong_rhythm".

    return results
