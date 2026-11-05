# MelodyMate keyboard-learning update

## Included
- Realistic 88-key piano layout, with white and black keys positioned as on a piano.
- Full standard piano range: A0 (MIDI 21) through C8 (MIDI 108).
- Horizontal scrolling for the complete keyboard and octave filtering for focused practice.
- Selected-key state, note playback, and spoken note names.
- A guided C-major note-identification exercise with spoken prompts, target-note playback, retry feedback, and octave highlighting.
- Screen-reader labels and live status announcements for keyboard actions.

## Validation performed
- `node --check app/static/app.js`
- `python -m compileall -q app core`
- `pytest -q tests/test_keyboard_ui.py` — 3 passed

The complete test suite was started (140 tests collected) but did not finish within the available execution window. It stalled during `tests/test_api.py::test_one_wrong_note_scores_7_of_8`; therefore, full-suite validation is still outstanding.

## Run locally
From the `melodymate` project folder, install dependencies from `requirements.txt` and run the existing start script or launch the FastAPI app using the instructions in `README.md`.
