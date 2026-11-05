"""
core/midi_input.py
------------------
Read note events from a MIDI keyboard (or a fake source for testing).

The hardware-reading code lives inside MidiReader.
Tests use FakeMidiReader, which has the identical interface.
"""

from __future__ import annotations

import queue
import time
from dataclasses import dataclass, field
from typing import Protocol

# python-rtmidi is only imported when actually opening a real device.
# This allows tests to run on machines without MIDI hardware.
try:
    import rtmidi
    _RTMIDI_AVAILABLE = True
except ImportError:
    _RTMIDI_AVAILABLE = False


# ── Data class ─────────────────────────────────────────────────────────────────

@dataclass
class NoteEvent:
    """One MIDI note-on or note-off event."""
    midi_number: int
    note_name: str          # e.g. "C4"
    velocity: int           # 0–127; velocity 0 on note-on means note-off
    timestamp: float        # seconds since some reference point
    is_note_on: bool        # True for note-on (velocity > 0)


# ── Interface protocol (for type checking) ────────────────────────────────────

class MidiReaderInterface(Protocol):
    def list_devices(self) -> list[str]: ...
    def open(self, device_index: int) -> None: ...
    def close(self) -> None: ...
    def get_events(self) -> list[NoteEvent]: ...


# ── Real MIDI reader ──────────────────────────────────────────────────────────

class MidiReader:
    """
    Reads MIDI note events from a real MIDI input device via python-rtmidi.

    Usage:
        reader = MidiReader()
        print(reader.list_devices())
        reader.open(0)
        events = reader.get_events()   # call repeatedly
        reader.close()
    """

    def __init__(self):
        self._midi_in = None
        self._event_queue: queue.Queue[NoteEvent] = queue.Queue()
        self._open_time: float = 0.0

    def list_devices(self) -> list[str]:
        """Return the names of available MIDI input devices."""
        if not _RTMIDI_AVAILABLE:
            return []
        midi_in = rtmidi.MidiIn()
        names = midi_in.get_ports()
        del midi_in
        return names

    def open(self, device_index: int) -> None:
        """Open the MIDI input device at the given index."""
        if not _RTMIDI_AVAILABLE:
            raise RuntimeError(
                "python-rtmidi is not installed. "
                "Run: pip install python-rtmidi"
            )
        self._midi_in = rtmidi.MidiIn()
        self._open_time = time.perf_counter()
        self._midi_in.open_port(device_index)
        self._midi_in.set_callback(self._on_message)

    def close(self) -> None:
        """Close the MIDI device."""
        if self._midi_in is not None:
            self._midi_in.close_port()
            self._midi_in = None

    def _on_message(self, message_and_delta, data=None):
        """
        Callback invoked by rtmidi for each incoming MIDI message.

        message_and_delta is a tuple: ([status, note, velocity], delta_time_s).
        """
        message, delta = message_and_delta
        status = message[0] & 0xF0   # strip channel nibble

        NOTE_ON = 0x90
        NOTE_OFF = 0x80

        if status not in (NOTE_ON, NOTE_OFF):
            return   # ignore non-note messages

        note = message[1]
        vel = message[2]

        # note-on with velocity 0 is conventionally treated as note-off
        is_on = (status == NOTE_ON) and (vel > 0)

        # Import here to avoid circular dependency at module level
        from core.notes import midi_to_note_name
        # Use perf_counter for wall-clock timestamps consistent with open().
        timestamp = time.perf_counter() - self._open_time

        event = NoteEvent(
            midi_number=note,
            note_name=midi_to_note_name(note),
            velocity=vel,
            timestamp=timestamp,
            is_note_on=is_on,
        )
        self._event_queue.put(event)

    def get_events(self) -> list[NoteEvent]:
        """Drain and return all queued events since the last call."""
        events = []
        while not self._event_queue.empty():
            events.append(self._event_queue.get_nowait())
        return events


# ── Fake reader (for tests) ───────────────────────────────────────────────────

class FakeMidiReader:
    """
    A drop-in replacement for MidiReader that accepts pre-fed events.

    Use this in tests so no MIDI hardware is needed.
    """

    def __init__(self):
        self._events: list[NoteEvent] = []
        self._returned = False

    def feed(self, events: list[NoteEvent]) -> None:
        """Pre-load events to be returned by get_events()."""
        self._events = list(events)
        self._returned = False

    # The rest of the interface mirrors MidiReader

    def list_devices(self) -> list[str]:
        return ["Fake MIDI Device"]

    def open(self, device_index: int) -> None:
        pass   # nothing to open for fake events

    def close(self) -> None:
        pass

    def get_events(self) -> list[NoteEvent]:
        """Return all pre-loaded events on first call, then empty list."""
        if not self._returned:
            self._returned = True
            return list(self._events)
        return []


# ── Conversion utility ────────────────────────────────────────────────────────

def events_to_midi_numbers(events: list[NoteEvent]) -> list[int]:
    """
    Filter events to note-on events only, sort by timestamp (then by MIDI number
    to break ties on identical timestamps), return MIDI numbers in that order.

    This produces the ordered list of played notes for Phase 2 comparison.
    """
    note_ons = [e for e in events if e.is_note_on]
    note_ons.sort(key=lambda e: (e.timestamp, e.midi_number))
    return [e.midi_number for e in note_ons]


# ── No-device message ─────────────────────────────────────────────────────────

def no_device_message() -> str:
    """Return a clear message when no MIDI devices are found."""
    return (
        "No MIDI input devices were found.\n"
        "Please connect your MIDI keyboard and try again.\n"
        "To verify the connection on Windows:\n"
        "  1. Open Device Manager (press Win+X, then select Device Manager).\n"
        "  2. Expand 'Sound, video and game controllers'.\n"
        "  3. Your keyboard should appear there. If it shows a warning icon,\n"
        "     right-click it and choose 'Update driver'."
    )
