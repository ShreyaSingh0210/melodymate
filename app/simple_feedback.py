"""app/simple_feedback.py: a short, beginner-friendly result for speaking aloud.
No note letters, no cents. At most one example problem."""
from __future__ import annotations

NOTHING = "I did not hear any singing. Check that your microphone is on, and sing a little louder."
_NTH = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth"]


def _nth(n: int) -> str:
    return f"the {_NTH[n - 1]} note" if 1 <= n <= 10 else f"note number {n}"


def simple_feedback(results) -> str:
    ref = [r for r in results if r.label != "extra"]
    if not ref or all(r.label == "missing" for r in ref):
        return NOTHING
    total = len(ref)
    right = sum(1 for r in ref if r.label == "correct")
    if right == total and not any(r.label == "extra" for r in results):
        return f"Well done. You sang all {total} notes right."
    share = right / total
    praise = "Well done." if share >= 0.9 else "Good try." if share >= 0.6 else "Keep practicing."
    text = f"{praise} You sang {right} out of {total} notes right."
    first = next(r for r in results if r.label in ("wrong", "missing", "extra"))
    if first.label == "wrong" and first.cents_error is not None:
        text += f" For example, {_nth(first.position)} was too {'high' if first.cents_error > 0 else 'low'}."
    elif first.label == "missing":
        text += f" For example, you missed {_nth(first.position)}."
    elif first.label == "extra":
        text += " For example, you sang one extra note."
    return text
