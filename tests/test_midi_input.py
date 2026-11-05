"""
tests/test_midi_input.py
------------------------
Tests for core/midi_input.py  (Phase 3).

All tests use FakeMidiReader — no MIDI hardware required.
"""

import pytest

from core.midi_input import FakeMidiReader, NoteEvent, events_to_midi_numbers
from core.notes import midi_to_note_name


# ── Helper: build a NoteEvent quickly ────────────────────────────────────────

def make_event(midi, velocity=80, timestamp=0.0):
    """Create a NoteEvent with is_note_on derived from velocity."""
    return NoteEvent(
        midi_number=midi,
        note_name=midi_to_note_name(midi),
        velocity=velocity,
        timestamp=timestamp,
        is_note_on=(velocity > 0),
    )


# ── FakeMidiReader interface ──────────────────────────────────────────────────

class TestFakeMidiReader:
    def test_list_devices(self):
        reader = FakeMidiReader()
        devices = reader.list_devices()
        assert len(devices) >= 1

    def test_open_close_no_error(self):
        reader = FakeMidiReader()
        reader.open(0)
        reader.close()

    def test_get_events_returns_fed_events(self):
        reader = FakeMidiReader()
        events = [make_event(60), make_event(62)]
        reader.feed(events)
        reader.open(0)
        result = reader.get_events()
        assert len(result) == 2

    def test_get_events_empty_after_first_call(self):
        reader = FakeMidiReader()
        reader.feed([make_event(60)])
        reader.open(0)
        reader.get_events()          # consume
        result = reader.get_events() # should be empty now
        assert result == []


# ── events_to_midi_numbers ────────────────────────────────────────────────────

class TestEventsToMidiNumbers:
    def test_ordered_notes(self):
        events = [
            make_event(60, timestamp=0.0),
            make_event(62, timestamp=0.1),
            make_event(64, timestamp=0.2),
        ]
        result = events_to_midi_numbers(events)
        assert result == [60, 62, 64]

    def test_velocity_zero_treated_as_note_off(self):
        events = [
            make_event(60, velocity=80, timestamp=0.0),  # note-on
            make_event(60, velocity=0,  timestamp=0.1),  # note-off (vel=0)
            make_event(62, velocity=80, timestamp=0.2),  # note-on
        ]
        result = events_to_midi_numbers(events)
        # Only the two genuine note-ons should appear
        assert result == [60, 62]

    def test_chord_within_30ms(self):
        # Notes within 30 ms of each other count as separate notes,
        # sorted by timestamp (and midi number for equal timestamps).
        events = [
            make_event(64, timestamp=0.000),   # E4
            make_event(60, timestamp=0.010),   # C4, 10 ms later
            make_event(67, timestamp=0.025),   # G4, 25 ms later
        ]
        result = events_to_midi_numbers(events)
        # All three are note-on; sorted by timestamp
        assert result == [64, 60, 67]

    def test_no_events(self):
        result = events_to_midi_numbers([])
        assert result == []

    def test_only_note_offs(self):
        events = [
            make_event(60, velocity=0, timestamp=0.0),
            make_event(62, velocity=0, timestamp=0.1),
        ]
        result = events_to_midi_numbers(events)
        assert result == []

    def test_sort_by_timestamp(self):
        # Feed events out of order; result should be time-sorted
        events = [
            make_event(67, timestamp=0.3),
            make_event(60, timestamp=0.0),
            make_event(64, timestamp=0.1),
        ]
        result = events_to_midi_numbers(events)
        assert result == [60, 64, 67]
