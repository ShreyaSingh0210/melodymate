"""
tools/check_midi.py
-------------------
Print each note as it is pressed on a connected MIDI keyboard.

Usage (run from the melodymate/ project root):
    python -m tools.check_midi

Press Ctrl-C to exit.
"""

import sys
import time

from core.midi_input import MidiReader, no_device_message


def main():
    reader = MidiReader()
    devices = reader.list_devices()

    if not devices:
        print(no_device_message())
        sys.exit(1)

    # If there is only one device, use it automatically.
    if len(devices) == 1:
        device_index = 0
        print(f"Using MIDI device: {devices[0]}")
    else:
        print("Available MIDI input devices:")
        for i, name in enumerate(devices):
            print(f"  {i}: {name}")
        raw = input("Enter device number: ").strip()
        try:
            device_index = int(raw)
        except ValueError:
            print("Invalid selection. Exiting.")
            sys.exit(1)

    reader.open(device_index)
    print("Ready. Press keys on your keyboard. Press Ctrl-C to stop.\n")

    try:
        while True:
            events = reader.get_events()
            for event in events:
                if event.is_note_on:
                    print(
                        f"{event.note_name} (MIDI {event.midi_number})"
                        f" velocity {event.velocity}"
                        f" at {event.timestamp:.3f}s"
                    )
            time.sleep(0.01)   # poll every 10 ms
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        reader.close()


if __name__ == "__main__":
    main()
