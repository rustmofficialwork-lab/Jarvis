import unittest

from voice_permission import normalize_spoken_text, parse_voice_approval


class VoicePermissionTests(unittest.TestCase):
    def test_exact_approval_phrase_is_accepted(self):
        self.assertIs(parse_voice_approval("JARVIS, approve amber.", "amber"), True)

    def test_exact_denial_phrase_is_accepted(self):
        self.assertIs(parse_voice_approval("Jarvis deny cobalt", "cobalt"), False)

    def test_generic_yes_is_not_approval(self):
        self.assertIsNone(parse_voice_approval("yes", "amber"))

    def test_wrong_challenge_is_rejected(self):
        self.assertIsNone(parse_voice_approval("jarvis approve amber", "cobalt"))

    def test_extra_words_are_rejected(self):
        self.assertIsNone(parse_voice_approval("please jarvis approve amber", "amber"))

    def test_empty_or_unrecognized_speech_fails_closed(self):
        self.assertIsNone(parse_voice_approval("", "amber"))
        self.assertEqual(normalize_spoken_text(""), "")


if __name__ == "__main__":
    unittest.main()
