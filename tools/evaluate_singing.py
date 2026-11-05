"""
tools/evaluate_singing.py
-------------------------
Benchmark evaluation harness for singing pitch tracking and segmentation.
Measures note detection accuracy across a multi-recording test suite.
"""
from __future__ import annotations

import sys
from pathlib import Path
from core.pitch import track_pitch
from core.segment import segment_notes
from core.melody import MELODIES, compare

ROOT = Path(__file__).resolve().parent.parent

TEST_SUITE = [
    {
        "name": "User Take (sing.wav.wav)",
        "file": ROOT / "sing.wav.wav",
        "melody": "mary_lamb",
        "mode": "relative",
        "description": "Real voice: Mary Had a Little Lamb in C# (+1), onset scoop, legato, drift",
    },
    {
        "name": "C Major Scale Up with Scoops",
        "file": ROOT / "tests" / "test_audio" / "test_c_major_up_scoops.wav",
        "melody": "c_major_up",
        "mode": "exact",
        "description": "Synth vocal: C major scale ascending with onset scoops on C4 and F4",
    },
    {
        "name": "C Major Scale Down with Drift & Vibrato",
        "file": ROOT / "tests" / "test_audio" / "test_c_major_down_drift.wav",
        "melody": "c_major_down",
        "mode": "exact",
        "description": "Synth vocal: C major scale descending with 5Hz vibrato and downward drift",
    },
    {
        "name": "Mary Had a Little Lamb (Legato in D)",
        "file": ROOT / "tests" / "test_audio" / "test_mary_lamb_legato.wav",
        "melody": "mary_lamb",
        "mode": "relative",
        "description": "Synth vocal: Mary Had a Little Lamb in D (+2) with legato repeated notes",
    },
]


def run_evaluation() -> tuple[list[dict], float]:
    results = []
    total_correct = 0
    total_reference = 0

    print("=" * 70)
    print("MELODYMATE SINGING DETECTION BENCHMARK")
    print("=" * 70)

    for item in TEST_SUITE:
        path = item["file"]
        if not path.exists():
            print(f"[MISSING] {path}")
            continue

        pr = track_pitch(path)
        notes = segment_notes(pr)
        perf_midis = [n.midi_float for n in notes]
        cmp_res = compare(MELODIES[item["melody"]], perf_midis, mode=item["mode"])

        ref_notes = [r for r in cmp_res if r.label != "extra"]
        correct = sum(1 for r in ref_notes if r.label == "correct")
        ref_count = len(ref_notes)
        extras = sum(1 for r in cmp_res if r.label == "extra")
        missing = sum(1 for r in cmp_res if r.label == "missing")
        wrong = sum(1 for r in cmp_res if r.label == "wrong")
        pct = (correct / ref_count * 100.0) if ref_count else 0.0

        total_correct += correct
        total_reference += ref_count

        res_info = {
            "name": item["name"],
            "melody": item["melody"],
            "mode": item["mode"],
            "correct": correct,
            "total": ref_count,
            "pct": pct,
            "detected_count": len(notes),
            "extras": extras,
            "missing": missing,
            "wrong": wrong,
            "shift_used": cmp_res.shift_used,
        }
        results.append(res_info)

        print(f"\n* {item['name']} ({item['melody']}, mode={item['mode']})")
        print(f"  Description: {item['description']}")
        print(f"  Score: {correct} / {ref_count} ({pct:.1f}%) | Detected notes: {len(notes)}")
        print(f"  Breakdown: {correct} correct, {wrong} wrong, {missing} missing, {extras} extra | Shift: {cmp_res.shift_used:+d}")

    avg_pct = (total_correct / total_reference * 100.0) if total_reference else 0.0
    print("\n" + "=" * 70)
    print(f"OVERALL SUITE AVERAGE: {total_correct} / {total_reference} ({avg_pct:.1f}%)")
    print("=" * 70)
    return results, avg_pct


if __name__ == "__main__":
    run_evaluation()
