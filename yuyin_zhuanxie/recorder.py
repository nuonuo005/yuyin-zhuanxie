from __future__ import annotations

import tempfile
import wave
import os
from pathlib import Path

import numpy as np


class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._stream = None
        self._frames: list[np.ndarray] = []

    def start(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("缺少 sounddevice，无法录音。请运行 install.ps1 重新安装依赖。") from exc

        if self._stream is not None:
            return

        self._frames = []

        def callback(indata, frames, time, status) -> None:
            if status:
                return
            self._frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=callback,
        )
        self._stream.start()

    def stop(self) -> Path:
        if self._stream is None:
            raise RuntimeError("当前没有正在录制的音频。")

        self._stream.stop()
        self._stream.close()
        self._stream = None

        if not self._frames:
            raise RuntimeError("没有录到声音，请检查麦克风权限或输入设备。")

        audio = np.concatenate(self._frames, axis=0)
        audio = np.clip(audio, -1.0, 1.0)
        pcm = (audio * 32767).astype(np.int16)

        fd, name = tempfile.mkstemp(prefix="yuyin_zhuanxie_", suffix=".wav")
        os.close(fd)
        path = Path(name)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm.tobytes())
        return path
