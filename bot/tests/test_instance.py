import tempfile
import unittest
from pathlib import Path

from flowerbot.config import ConfigError
from flowerbot.instance import SingleInstance


class SingleInstanceTests(unittest.TestCase):
    def test_second_process_gets_clear_error_and_can_start_after_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bot.lock'
            first, second = SingleInstance(path), SingleInstance(path)
            first.acquire()
            with self.assertRaises(ConfigError):
                second.acquire()
            first.release()
            second.acquire()
            second.release()
