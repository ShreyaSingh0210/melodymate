"""Timing feedback based on melody beat lengths and segmented sung notes."""

from __future__ import annotations

from statistics import median


def timing_feedback(results, sung_notes, expected_beats: list[float]) -> str:
    """Describe note lengths relative to the melody, independent of tempo.

    The singer's tempo is estimated from the median observed seconds per beat.
    Insertions and omissions follow the same edit alignment used for pitch so
    they do not shift the timing comparison for later notes.
    """
    matched: list[tuple[int, float, float]] = []
    performance_index = 0
    for result in results:
        if result.label == "extra":
            performance_index += 1
            continue
        if result.label == "missing":
            continue
        if performance_index >= len(sung_notes):
            break
        if 1 <= result.position <= len(expected_beats):
            note = sung_notes[performance_index]
            beats = expected_beats[result.position - 1]
            duration = max(0.0, float(note.end_time) - float(note.start_time))
            if beats > 0 and duration > 0:
                matched.append((result.position, duration, beats))
        performance_index += 1

    if len(matched) < 2:
        return ""

    seconds_per_beat = median(duration / beats for _, duration, beats in matched)
    if seconds_per_beat <= 0:
        return ""

    issues = []
    for position, duration, beats in matched:
        ratio = duration / (seconds_per_beat * beats)
        if ratio < 0.62:
            issues.append(f"Note {position} was held too briefly.")
        elif ratio > 1.55:
            issues.append(f"Note {position} was held longer than the melody suggests.")
        if len(issues) == 2:
            break

    if issues:
        return " ".join(issues)
    return "Your note lengths were close to the melody's rhythm."
