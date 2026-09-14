import unittest
from unittest.mock import Mock, patch

from terminal import Display, Terminal


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

    def test_until_accepts_state_already_visible_without_pumping(self):
        terminal = Terminal.__new__(Terminal)
        terminal.display = Display(lambda _reply: None)
        terminal.display.feed("target")
        terminal.pump = Mock(side_effect=AssertionError("pump should not run for an existing match"))

        with patch("terminal.time.perf_counter", side_effect=[10.0, 10.0]):
            matched_at = terminal.until(lambda display: "target" in display.text(), 0.1)

        self.assertEqual(matched_at, 10.0)
        terminal.pump.assert_not_called()


if __name__ == "__main__":
    unittest.main()
