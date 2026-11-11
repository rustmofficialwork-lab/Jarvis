from __future__ import annotations

import json
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from owner_voice_verification import (
    DEFAULT_COSINE_THRESHOLD,
    MODEL_ID,
    MODEL_REVISION,
    PROFILE_SCHEMA,
    PROFILE_SERVICE,
    PROFILE_USERNAME,
    build_owner_profile,
    delete_owner_profile,
    load_owner_profile,
    save_owner_profile,
    verify_samples,
)


class FakeEncoder:
    def __init__(self, vector=None):
        self.vector = np.asarray(
            vector if vector is not None else [1.0, 0.0, 0.0], dtype=np.float32
        )

    def run(self, _outputs, inputs):
        self.last_inputs = inputs
        return [self.vector.reshape(1, 1, -1)]


class MemoryKeyring:
    def __init__(self):
        self.values = {}

    def set_password(self, service, username, password):
        self.values[(service, username)] = password

    def get_password(self, service, username):
        return self.values.get((service, username))

    def delete_password(self, service, username):
        self.values.pop((service, username), None)


class OwnerVoiceVerificationTests(unittest.TestCase):
    def _write_clip(self, path: Path):
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16_000)
            output.writeframes(
                (np.ones(16_000 * 3, dtype="<i2") * 2000).tobytes()
            )

    def test_profile_requires_five_clips_and_builds_centroid(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for index in range(5):
                path = Path(directory) / f"owner-{index}.wav"
                self._write_clip(path)
                paths.append(path)
            profile = build_owner_profile(paths, FakeEncoder())
        self.assertEqual(profile["sample_count"], 5)
        self.assertEqual(profile["schema"], PROFILE_SCHEMA)
        self.assertEqual(profile["model_id"], MODEL_ID)
        self.assertEqual(profile["model_revision"], MODEL_REVISION)
        self.assertEqual(len(profile["embedding"]), 3)
        self.assertAlmostEqual(profile["embedding"][0], 1.0, places=5)

    def test_profile_is_stored_in_credential_store_and_can_be_deleted(self):
        keyring = MemoryKeyring()
        profile = {
            "schema": PROFILE_SCHEMA,
            "model_id": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "embedding": [3.0, 0.0, 0.0],
            "sample_count": 5,
        }
        save_owner_profile(profile, keyring_module=keyring)
        loaded = load_owner_profile(keyring_module=keyring)
        self.assertAlmostEqual(loaded["embedding"][0], 1.0)
        self.assertIn((PROFILE_SERVICE, PROFILE_USERNAME), keyring.values)
        self.assertIsInstance(json.loads(keyring.values[(PROFILE_SERVICE, PROFILE_USERNAME)]), dict)
        delete_owner_profile(keyring_module=keyring)
        self.assertIsNone(load_owner_profile(keyring_module=keyring))

    def test_verification_rejects_missing_profile_and_accepts_matching_vector(self):
        samples = np.ones(16_000 * 3, dtype=np.float32)
        accepted, score = verify_samples(samples, FakeEncoder(), None)
        self.assertFalse(accepted)
        self.assertIsNone(score)
        profile = {"embedding": [1.0, 0.0, 0.0]}
        accepted, score = verify_samples(samples, FakeEncoder(), profile)
        self.assertTrue(accepted)
        self.assertGreaterEqual(score, DEFAULT_COSINE_THRESHOLD)

    def test_verification_rejects_nonmatching_speaker_vector(self):
        samples = np.ones(16_000 * 3, dtype=np.float32)
        profile = {"embedding": [1.0, 0.0, 0.0]}
        accepted, score = verify_samples(
            samples, FakeEncoder(vector=[0.0, 1.0, 0.0]), profile
        )
        self.assertFalse(accepted)
        self.assertAlmostEqual(score, 0.0, places=5)

    def test_verification_fails_closed_for_short_audio_and_mismatched_vectors(self):
        accepted, score = verify_samples(
            np.ones(100, dtype=np.float32),
            FakeEncoder(),
            {"embedding": [1, 0, 0]},
        )
        self.assertFalse(accepted)
        self.assertIsNone(score)
        accepted, score = verify_samples(
            np.ones(16_000 * 3, dtype=np.float32),
            FakeEncoder(),
            {"embedding": [1, 0]},
        )
        self.assertFalse(accepted)
        self.assertIsNone(score)


if __name__ == "__main__":
    unittest.main()
