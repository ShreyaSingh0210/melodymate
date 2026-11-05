from app.simple_feedback import NOTHING, simple_feedback
from core.melody import NoteResult


def r(label, pos, cents=0.0):
    return NoteResult(label=label, ref_midi=60, perf_midi=60.0, cents_error=cents, position=pos)


def test_all_right():
    assert simple_feedback([r("correct", i) for i in range(1, 9)]) == "Well done. You sang all 8 notes right."


def test_one_wrong_high():
    res = [r("correct", 1), r("correct", 2), r("correct", 3), r("wrong", 4, 120.0)]
    text = simple_feedback(res)
    assert "3 out of 4" in text and "the fourth note was too high" in text and "#" not in text


def test_wrong_low():
    assert "too low" in simple_feedback([r("correct", 1), r("wrong", 2, -150.0)])


def test_missing_note():
    assert "you missed the second note" in simple_feedback([r("correct", 1), r("missing", 2), r("correct", 3)])


def test_nothing_heard():
    assert simple_feedback([r("missing", 1), r("missing", 2)]) == NOTHING
    assert simple_feedback([]) == NOTHING


def test_long_melody_uses_number():
    assert "note number 14" in simple_feedback([r("correct", 1), r("wrong", 14, 90.0)])


def test_short_and_plain():
    res = [r("wrong", i, 100.0) for i in range(1, 6)] + [r("correct", 6)]
    assert len(simple_feedback(res).split()) < 25
