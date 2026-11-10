from __future__ import annotations

import wave

from wakeword_dataset_audit import audit_dataset, inspect_wav


def _write_wav(path, *, rate=16_000, frames=16_000, amplitude=4000):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        sample = int(amplitude).to_bytes(2, "little", signed=True)
        output.writeframes(sample * frames)


def test_inspect_wav_accepts_valid_local_clip(tmp_path):
    path = tmp_path / "positive.wav"
    _write_wav(path)
    result = inspect_wav(path)
    assert result["valid"] is True
    assert result["sample_rate"] == 16_000
    assert result["duration_seconds"] == 1.0


def test_inspect_wav_reports_wrong_sample_rate(tmp_path):
    path = tmp_path / "wrong-rate.wav"
    _write_wav(path, rate=8_000)
    result = inspect_wav(path)
    assert result["valid"] is False
    assert "expected 16000 Hz" in result["issues"]


def test_audit_requires_both_classes(tmp_path):
    (tmp_path / "positive").mkdir()
    (tmp_path / "negative").mkdir()
    _write_wav(tmp_path / "positive" / "one.wav")
    report = audit_dataset(tmp_path)
    assert report["status"] == "needs-attention"
    assert "missing or empty negative/ folder" in report["issues"]
