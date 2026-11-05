"""Tests for the web API, using synthetic audio only (no microphone, no browser)."""
import io

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app.main import app
from core.melody import MELODIES
from core.synth import write_melody_wav

client = TestClient(app)


def post(data: bytes, melody="c_major_up", mode="exact"):
    return client.post(
        "/api/analyze/singing",
        files={"file": ("a.wav", data, "audio/wav")},
        data={"melody": melody, "mode": mode},
    )


def wav_bytes(tmp_path, midi_numbers):
    path = tmp_path / "s.wav"
    write_melody_wav(midi_numbers, path)
    return path.read_bytes()


def silent_wav(seconds, rate=8000):
    buf = io.BytesIO()
    sf.write(buf, np.zeros(int(seconds * rate)), rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_page_is_served():
    r = client.get("/")
    assert r.status_code == 200 and "<h1>" in r.text


def test_melody_list():
    ids = [m["id"] for m in client.get("/api/melodies").json()]
    assert "c_major_up" in ids and "mary_lamb" in ids


def test_reference_is_a_valid_wav():
    r = client.get("/api/reference/c_major_up")
    assert r.status_code == 200
    audio, rate = sf.read(io.BytesIO(r.content))
    assert len(audio) > rate  # more than one second of audio


def test_reference_unknown_melody():
    assert client.get("/api/reference/nope").status_code == 404


def test_perfect_scale_scores_8_of_8(tmp_path):
    r = post(wav_bytes(tmp_path, MELODIES["c_major_up"]))
    assert r.status_code == 200
    body = r.json()
    assert "8 of 8" in body["feedback"]
    assert body["detected_notes"][0] == "C 4"


def test_one_wrong_note_scores_7_of_8(tmp_path):
    wrong = list(MELODIES["c_major_up"])
    wrong[3] = 66  # F sharp instead of F
    r = post(wav_bytes(tmp_path, wrong))
    assert r.status_code == 200
    assert "7 of 8" in r.json()["feedback"]


def test_not_a_wav():
    assert post(b"this is not audio").status_code == 400


def test_oversized_file():
    assert post(b"\0" * (10 * 1024 * 1024 + 1)).status_code == 413


def test_too_long():
    assert post(silent_wav(61)).status_code == 400


def test_too_short():
    assert post(silent_wav(0.2)).status_code == 400


@pytest.mark.parametrize("melody,mode", [("nope", "exact"), ("c_major_up", "nope")])
def test_unknown_melody_or_mode(melody, mode):
    assert post(silent_wav(1), melody, mode).status_code == 400
