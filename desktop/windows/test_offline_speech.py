import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock

from offline_speech import (
    MODEL_CATALOG,
    OfflineModelUnavailable,
    install_offline_model,
    model_path_for_language,
    transcribe_offline_vosk,
)


class OfflineSpeechTests(unittest.TestCase):
    def test_language_models_have_distinct_local_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            hindi = model_path_for_language("hi-IN", Path(temp))
            english = model_path_for_language("en-IN", Path(temp))
            self.assertNotEqual(hindi, english)
            self.assertEqual(hindi.name, MODEL_CATALOG["hi-IN"][0])

    def test_missing_model_is_reported_without_network_fallback(self):
        audio = Mock()
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(OfflineModelUnavailable):
                transcribe_offline_vosk(audio, "hi-IN", Path(temp))
        audio.get_raw_data.assert_not_called()

    def test_transcription_uses_16khz_pcm_and_returns_text(self):
        class FakeRecognizer:
            def __init__(self, _model, rate):
                self.rate = rate
            def AcceptWaveform(self, raw):
                self.raw = raw
            def FinalResult(self):
                return json.dumps({"text": "notepad kholo"})
        fake_vosk = Mock()
        fake_vosk.KaldiRecognizer.side_effect = FakeRecognizer
        fake_vosk.Model.return_value = "loaded-model"
        audio = Mock()
        audio.get_raw_data.return_value = b"pcm"
        with tempfile.TemporaryDirectory() as temp:
            model_path_for_language("hi-IN", Path(temp)).mkdir()
            result = transcribe_offline_vosk(audio, "hi-IN", Path(temp), fake_vosk)
        self.assertEqual(result, "notepad kholo")
        audio.get_raw_data.assert_called_once_with(convert_rate=16000, convert_width=2)
        self.assertEqual(fake_vosk.KaldiRecognizer.call_args.args[1], 16000)

    def test_installer_extracts_model_to_requested_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            archive_bytes = io.BytesIO()
            model_name = MODEL_CATALOG["hi-IN"][0]
            with zipfile.ZipFile(archive_bytes, "w") as archive:
                archive.writestr(model_name + "/conf/model.conf", "test")
            payload = archive_bytes.getvalue()
            def fake_urlopen(_url, timeout):
                self.assertEqual(timeout, 30)
                return io.BytesIO(payload)
            installed = install_offline_model("hi-IN", Path(temp), fake_urlopen)
            self.assertEqual(installed.name, model_name)
            self.assertTrue((installed / "conf/model.conf").is_file())
            self.assertEqual(install_offline_model("hi-IN", Path(temp), fake_urlopen), installed)

    def test_installer_rejects_zip_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            archive_bytes = io.BytesIO()
            with zipfile.ZipFile(archive_bytes, "w") as archive:
                archive.writestr("../outside.txt", "unsafe")
            with self.assertRaisesRegex(RuntimeError, "unsafe file path"):
                install_offline_model(
                    "hi-IN", Path(temp), lambda _url, timeout: io.BytesIO(archive_bytes.getvalue())
                )
            self.assertFalse((Path(temp).parent / "outside.txt").exists())


    def test_installer_rejects_files_outside_expected_model_root(self):
        with tempfile.TemporaryDirectory() as temp:
            archive_bytes = io.BytesIO()
            with zipfile.ZipFile(archive_bytes, "w") as archive:
                archive.writestr("other-folder/payload.txt", "unexpected")
            with self.assertRaisesRegex(RuntimeError, "unsafe file path"):
                install_offline_model(
                    "hi-IN", Path(temp), lambda _url, timeout: io.BytesIO(archive_bytes.getvalue())
                )

    def test_installer_rejects_symbolic_links(self):
        import stat
        with tempfile.TemporaryDirectory() as temp:
            archive_bytes = io.BytesIO()
            info = zipfile.ZipInfo(MODEL_CATALOG["hi-IN"][0] + "/link")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(archive_bytes, "w") as archive:
                archive.writestr(info, "target")
            with self.assertRaisesRegex(RuntimeError, "symbolic link"):
                install_offline_model(
                    "hi-IN", Path(temp), lambda _url, timeout: io.BytesIO(archive_bytes.getvalue())
                )

    def test_installer_rejects_excessive_expanded_archive_size(self):
        from unittest.mock import patch
        class FakeMember:
            filename = MODEL_CATALOG["hi-IN"][0] + "/large.bin"
            file_size = 500 * 1024 * 1024 + 1
        class FakeArchive:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def infolist(self):
                return [FakeMember()]
        with tempfile.TemporaryDirectory() as temp:
            def fake_urlopen(_url, timeout):
                return io.BytesIO(b"not-used")
            with patch("offline_speech.zipfile.ZipFile", return_value=FakeArchive()):
                with self.assertRaisesRegex(RuntimeError, "500 MB"):
                    install_offline_model("hi-IN", Path(temp), fake_urlopen)


if __name__ == "__main__":
    unittest.main()
