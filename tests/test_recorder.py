from __future__ import annotations

import sys
import unittest
import wave
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from yuyin_zhuanxie.recorder import AudioRecorder


class _FakeStream:
    def __init__(self, callback, **_kwargs) -> None:
        self.callback = callback

    def start(self) -> None:
        data = np.full((1600, 1), 0.1, dtype=np.float32)
        self.callback(data, len(data), None, None)

    def stop(self) -> None:
        return

    def close(self) -> None:
        return


class RecorderTests(unittest.TestCase):
    def test_streams_to_wave_file(self) -> None:
        fake_module = SimpleNamespace(InputStream=_FakeStream)
        with patch.dict(sys.modules, {"sounddevice": fake_module}):
            recorder = AudioRecorder()
            recorder.start()
            path = recorder.stop()
        try:
            self.assertTrue(path.exists())
            with wave.open(str(path), "rb") as audio:
                self.assertEqual(audio.getframerate(), 16000)
                self.assertEqual(audio.getnchannels(), 1)
                self.assertGreater(audio.getnframes(), 0)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
