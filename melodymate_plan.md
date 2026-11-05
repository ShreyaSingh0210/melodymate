# MelodyMate — Implementation Plan (Phases 1–6)

> [!IMPORTANT]
> This is the plan for your approval. No code has been written yet. Please review and confirm before I begin.

---

## Project Layout

```
melodymate/
  core/
    notes.py
    melody.py
    feedback.py
    midi_input.py
    pitch.py
    segment.py
    synth.py
  tools/
    check_midi.py
    analyze_wav.py
  tests/
    test_notes.py
    test_melody.py
    test_feedback.py
    test_midi_input.py
    test_pitch.py
    test_segment.py
    test_synth.py
  README.md
  requirements.txt
  conftest.py          # shared pytest fixtures
```

---

## Phase 1 — `core/notes.py`

### Functions

| Function | Signature | Notes |
|---|---|---|
| `freq_to_midi` | `(freq: float) -> float` | Raises `ValueError` on zero, negative, NaN |
| `midi_to_note_name` | `(midi: float) -> str` | Rounds to nearest int; sharps only; returns e.g. `"C4"` |
| `note_name_to_midi` | `(name: str) -> int` | Inverse; supports `"C#4"` style |
| `cents_off` | `(freq: float) -> float` | Signed: negative = flat, positive = sharp |

### Constants
- `A4_MIDI = 69`, `A4_HZ = 440.0`
- Note name lookup table: list of 12 names (`["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]`)

### Tests (`tests/test_notes.py`)
- 261.63 Hz → C4 (within 1 cent)
- 440 Hz → A4
- 27.5 Hz → A0
- 4186 Hz → C8
- `freq_to_midi(0)` raises `ValueError`
- `freq_to_midi(-1)` raises `ValueError`
- `freq_to_midi(float('nan'))` raises `ValueError`
- `cents_off` on exact A4 → 0.0
- Round-trip: `note_name_to_midi("F#3")` → 54, `midi_to_note_name(54)` → `"F#3"`

---

## Phase 2 — `core/melody.py` + `core/feedback.py`

### `melody.py`

#### Reference melodies (stored as plain lists of MIDI ints)
```python
MELODIES = {
    "c_major_up":   [60, 62, 64, 65, 67, 69, 71, 72],
    "c_major_down": [72, 71, 69, 67, 65, 64, 62, 60],
    "mary_lamb":    [64, 62, 60, 62, 64, 64, 64,
                     62, 62, 62, 64, 67, 67,
                     64, 62, 60, 62, 64, 64, 64,
                     62, 62, 64, 62, 60],
}
```

#### `compare(reference, performed, mode="exact") -> list[NoteResult]`

**`NoteResult` dataclass:**
```python
@dataclass
class NoteResult:
    label: str          # "correct" | "wrong" | "missing" | "extra"
    ref_midi: int | None
    perf_midi: float | None   # float allows unrounded sung pitch
    cents_error: float | None # None for MIDI keyboard notes
    position: int             # 1-based position in reference
```

**Alignment strategy — Wagner–Fischer edit distance:**
- Costs: substitution = 1, insertion = 1, deletion = 1
- After alignment, walk the path and label each pair
- A note is *correct* if `|perf_midi - ref_midi| * 100 < CENTS_THRESHOLD` (= 50 cents)
- MIDI keyboard notes: `cents_error = 0.0` always

**Three modes:**
1. `"exact"` — compare as-is
2. `"ignore_octave"` — take `midi % 12` before comparison
3. `"relative"` — shift entire performance by `ref[0] - perf[0]`, then compare as exact

> [!NOTE]
> **Rhythm placeholder** — A clearly commented `# TODO(rhythm): add duration comparison here` block will be placed at the end of `compare()` where rhythm data can slot in.

#### Tests (`tests/test_melody.py`)
| Scenario | Expected |
|---|---|
| Perfect performance | All correct |
| One wrong note (4th) | 3 correct + 1 wrong |
| Missing first note | 1 missing + rest aligned |
| Missing last note | 1 missing at end |
| One extra note | 1 extra |
| Empty performance | All missing |
| C D E G vs C D E F | E correct, G wrong/extra |
| Note 60 cents high | Correct=False (> 50 ct threshold) |
| Note 30 cents high | Correct=True |
| Whole melody octave lower, mode=exact | All wrong |
| Whole melody octave lower, mode=ignore_octave | All correct |
| Whole melody octave lower, mode=relative | All correct |
| Melody a 4th higher, mode=relative | All correct |

### `feedback.py`

#### `generate_feedback(results, input_type="keyboard") -> str`

Rules encoded:
- First sentence: score ("You played/sang N of M notes correctly.")
- Per-error sentences: wrong → "Note N was X, expected Y."; missing → "You missed note N, X."; extra → "You played an extra note, X, at position N."
- Singing: include cents ("about N cents higher/lower than the reference")
- Note names spelled out: `"C sharp 4"`, `"F sharp 3"` (no `#` symbol)
- If no notes played/sung: "Nothing was detected. [device hint]."
- Under 45 words target for short melodies (≤5 notes)

#### Tests (`tests/test_feedback.py`)
- Perfect → starts with "You played 5 of 5 notes correctly."
- One wrong → contains the wrong note name spelled out
- Empty performance, keyboard → mentions checking connection
- Empty performance, singing → mentions microphone
- Cents error → "higher" or "lower" in output

---

## Phase 3 — `core/midi_input.py` + `tools/check_midi.py`

### `midi_input.py`

#### Key design: thin interface layer
```python
class NoteEvent:
    midi_number: int
    note_name: str
    velocity: int
    timestamp: float   # seconds
    is_note_on: bool

class MidiReader:
    def list_devices() -> list[str]           # class method
    def open(device_index: int) -> None
    def close() -> None
    def get_events() -> list[NoteEvent]       # drain the queue

class FakeMidiReader:                          # for tests only
    def feed(events: list[NoteEvent]) -> None
    # same interface as MidiReader
```

- `note_on` with velocity 0 → treated as `note_off`
- `events_to_midi_numbers(events) -> list[int]` — filters to note-on, sorts by timestamp

#### `check_midi.py`
- Prompts user to select device (or auto-selects if only one)
- Prints each `NoteEvent` as it arrives: `"C4 (MIDI 60) velocity 80"`
- Ctrl-C exits cleanly

#### Tests (`tests/test_midi_input.py`)
- Ordered notes via `FakeMidiReader`
- velocity-0 treated as note-off (not in output of `events_to_midi_numbers`)
- Chord (events within 30 ms) → both appear, sorted by midi number
- Empty event list → empty output

---

## Phase 4 — `core/pitch.py`

### `pitch.py`

#### `track_pitch(wav_path: str | Path) -> PitchResult`

```python
@dataclass
class PitchResult:
    times: np.ndarray       # seconds, shape (N,)
    freqs: np.ndarray       # Hz, NaN where unvoiced, shape (N,)
    voiced: np.ndarray      # bool, shape (N,)
```

- Loads WAV with `soundfile`, converts stereo → mono by averaging channels
- Calls `librosa.pyin(y, fmin=65.41, fmax=1046.5, sr=sr)`
- `FMIN = 65.41` (C2), `FMAX = 1046.5` (C6) as named constants

#### Tests (`tests/test_pitch.py`) — **synthetic audio only, no microphone**
- Use `numpy` to generate sine waves, write to temp WAV with `soundfile`
- Pure C4 (261.63 Hz): detected within 20 cents
- Pure A4 (440 Hz): detected within 20 cents
- Pure E3 (164.81 Hz): detected within 20 cents
- C4 with ±30 cent vibrato at 5 Hz: median detected within 20 cents
- C4 with added white noise (SNR ~20 dB): detected within 20 cents
- Silence: 0 voiced frames

---

## Phase 5 — `core/segment.py`

### Named constants at top of file
```python
PITCH_CHANGE_CENTS   = 70    # start new note if pitch deviates this much
UNVOICED_GAP_MS      = 80    # ms of silence → boundary
MIN_NOTE_MS          = 100   # discard notes shorter than this
GLITCH_FRAMES        = 2     # smooth up to this many anomalous frames
```

### `segment_notes(pitch_result: PitchResult) -> list[SungNote]`

```python
@dataclass
class SungNote:
    midi_float: float    # median MIDI pitch of the segment
    note_name: str       # nearest semitone name
    cents_off: float     # signed cents from nearest semitone
    start_time: float
    end_time: float
```

**Algorithm outline:**
1. Smooth glitches: replace isolated 1–2 frame anomalies (>70 ct from neighbours, including octave jumps) with interpolated values
2. Walk frames; maintain running buffer for current segment
3. Detect boundary on: unvoiced gap ≥ 80 ms OR pitch deviation > 70 ct from segment median
4. Discard segments < 100 ms

#### Tests (`tests/test_segment.py`) — synthetic audio
- C4 D4 E4 F4 with short silences → 4 notes, correct names
- Same with vibrato → 4 notes, names within 1 semitone
- Same with noise → 4 notes
- Two repeated C4 with 100 ms gap → 2 notes

---

## Phase 6 — `core/synth.py` + `tools/analyze_wav.py`

### `synth.py`

#### `write_melody_wav(midi_numbers, output_path, note_duration=0.5, sample_rate=44100)`
- Sine tones, 10 ms fade-in / 10 ms fade-out per note
- Pure Python + NumPy, no playback
- Silently overwrites output if it already exists

#### `analyze_wav.py` (CLI tool)
```
Usage: python tools/analyze_wav.py <wav_file> <melody_name> [mode]

Arguments:
  wav_file      Path to WAV file
  melody_name   One of: c_major_up, c_major_down, mary_lamb
  mode          exact | ignore_octave | relative  (default: exact)

Output (printed to stdout):
  Detected notes: C4, D4, E4, F4
  Feedback: You sang 4 of 4 notes correctly.
```

#### Tests (`tests/test_synth.py`)
- `write_melody_wav` produces a WAV of correct duration
- WAV is readable by `soundfile`
- Feeding the output through `pitch.py` + `segment.py` detects the correct notes (integration test)

---

## `requirements.txt` (what I'll write)

```
numpy
librosa
soundfile
mido
python-rtmidi
pytest
```

---

## README outline

1. **Windows setup** — Python 3.11/3.12, `pip install -r requirements.txt`, MIDI driver note
2. **Running tests** — `pytest tests/ -v`
3. **Using `check_midi.py`** — connect keyboard, run, press keys
4. **Recording a test WAV** — Windows Voice Recorder → export WAV (or Audacity)
5. **Using `analyze_wav.py`** — command-line example

---

## Open questions / assumptions I'll document

- `python-rtmidi` on Windows may need the VC++ redistributable; I'll note this.
- `librosa.pyin` frame size will use its defaults (hop_length=512, sr as loaded); I'll note actual values.
- Chord handling in Phase 3: notes within 30 ms counted as simultaneous; sort order within chord is by MIDI number ascending.
- I will **not** install or invoke any audio playback library (no `pygame`, `playsound`, etc.).
- `analyze_wav.py` assumes the input is already 16-bit PCM WAV; a note in README will say to convert if needed.

---

> [!NOTE]
> **Waiting for your approval.** Once you confirm, I will build the phases one at a time, run tests after each, and show you results before moving to the next.
