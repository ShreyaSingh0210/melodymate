from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_keyboard_learning_controls_are_present_and_accessible():
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    assert 'id="keyboard-octave"' in html
    assert 'id="piano-keys"' in html
    assert 'aria-live="polite"' in html
    assert 'id="play-keyboard-note"' in html
    assert 'id="announce-keyboard-note"' in html


def test_keyboard_client_loads_full_range_from_api():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert 'fetch("/api/piano/keys")' in js
    assert "midi < 21 || midi > 108" in js
    assert "All keys (A0–C8)" in js


def test_realistic_keyboard_and_guided_practice_controls_are_present():
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    assert 'class="piano-scroll"' in html
    assert 'id="start-note-exercise"' in html
    assert 'id="repeat-note-target"' in html
    assert 'id="note-exercise-prompt" role="status" aria-live="polite"' in html

    css = (ROOT / "app/static/style.css").read_text(encoding="utf-8")
    assert ".piano-key.white-key" in css
    assert ".piano-key.black-key" in css
    assert ".target-octave" in css

    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "const exerciseNotes = [60, 62, 64, 65, 67, 69, 71, 72]" in js
    assert "button.classList.toggle(\"target-octave\"" in js
    assert "button.setAttribute(\"aria-label\"" in js
