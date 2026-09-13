import unittest

from terminal import Display


class PromptReadinessTests(unittest.TestCase):
    def test_recognizes_current_and_legacy_prompt_bars(self):
        for text in ("agents/resume\r\n> ", ">\r\n← manage        unknown  0"):
            with self.subTest(text=text):
                display = Display(lambda _reply: None)
                display.feed(text)
                self.assertTrue(display.prompt_ready())

    def test_rejects_partial_prompt_signals(self):
        for text in ("Loading...", ">", "← manage"):
            with self.subTest(text=text):
                display = Display(lambda _reply: None)
                display.feed(text)
                self.assertFalse(display.prompt_ready())


if __name__ == "__main__":
    unittest.main()
