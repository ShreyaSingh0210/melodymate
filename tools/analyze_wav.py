"""
tools/analyze_wav.py
--------------------
Detect notes in a WAV file and print feedback against a reference melody.

Usage (run from the melodymate/ project root):
    python -m tools.analyze_wav <wav_file> <melody_name> [mode]

Arguments:
    wav_file      Path to the WAV file to analyse.
    melody_name   One of: c_major_up, c_major_down, mary_lamb
    mode          exact | ignore_octave | relative  (default: exact)

Example:
    python -m tools.analyze_wav my_recording.wav c_major_up exact
"""

import sys

from core.pitch import track_pitch
from core.segment import segment_notes
from core.melody import compare, MELODIES
from core.feedback import generate_feedback


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    wav_path = sys.argv[1]
    melody_name = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) >= 4 else "exact"

    # Validate melody name
    if melody_name not in MELODIES:
        print(f"Unknown melody '{melody_name}'. Choose from: {', '.join(MELODIES.keys())}")
        sys.exit(1)

    # Validate mode
    valid_modes = ("exact", "ignore_octave", "relative")
    if mode not in valid_modes:
        print(f"Unknown mode '{mode}'. Choose from: {', '.join(valid_modes)}")
        sys.exit(1)

    # Step 1: track pitch
    print(f"Analysing: {wav_path}")
    print(f"Melody: {melody_name}  |  Mode: {mode}\n")

    try:
        pitch_result = track_pitch(wav_path)
    except Exception as e:
        print(f"Error reading WAV file: {e}")
        sys.exit(1)

    # Step 2: segment into notes
    sung_notes = segment_notes(pitch_result)

    if sung_notes:
        note_list = ", ".join(n.note_name for n in sung_notes)
        print(f"Detected notes: {note_list}")
    else:
        print("No notes detected.")

    # Step 3: compare with reference
    reference = MELODIES[melody_name]
    performed = [n.midi_float for n in sung_notes]
    results = compare(reference, performed, mode=mode)

    # Step 4: generate and print feedback
    feedback = generate_feedback(results, input_type="singing", shift_used=results.shift_used)
    if mode == "relative" and results.shift_used != 0:
        direction = "up" if results.shift_used > 0 else "down"
        print(f"Relative mode: best shift = {results.shift_used:+d} semitones "
              f"({abs(results.shift_used)} semitone{'s' if abs(results.shift_used) != 1 else ''} {direction})")
    print(f"\nFeedback: {feedback}")


if __name__ == "__main__":
    main()
