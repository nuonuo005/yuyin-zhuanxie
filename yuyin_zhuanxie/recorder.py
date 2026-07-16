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
        self._wave_file: wave.Wave_write | None = None
        self._path: Path | None = None
        self._frames_written = 0
        self._callback_error = ""

    def start(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("缺少 sounddevice，无法录音。请运行 install.ps1 重新安装依赖。") from exc

        if self._stream is not None:
            return

        fd, name = tempfile.mkstemp(prefix="yuyin_zhuanxie_", suffix=".wav")
        os.close(fd)
        self._path = Path(name)
        self._frames_written = 0
        self._callback_error = ""
        self._wave_file = wave.open(str(self._path), "wb")
        self._wave_file.setnchannels(self.channels)
        self._wave_file.setsampwidth(2)
        self._wave_file.setframerate(self.sample_rate)

        def callback(indata, frames, time, status) -> None:
            if status:
                self._callback_error = str(status)
            try:
                audio = np.clip(indata, -1.0, 1.0)
                pcm = (audio * 32767).astype(np.int16)
                if self._wave_file is not None:
                    self._wave_file.writeframesraw(pcm.tobytes())
                    self._frames_written += frames
            except Exception as exc:
                self._callback_error = str(exc)

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                callback=callback,
            )
            self._stream.start()
        except Exception:
            self._close_wave()
            self._delete_temporary_path()
            self._stream = None
            raise

    def stop(self) -> Path:
        if self._stream is None:
            raise RuntimeError("当前没有正在录制的音频。")

        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None
            self._close_wave()

        if self._frames_written <= 0:
            self._delete_temporary_path()
            raise RuntimeError("没有录到声音，请检查麦克风权限或输入设备。")
        if self._callback_error:
            path = self._path
            self._path = None
            if path:
                path.unlink(missing_ok=True)
            raise RuntimeError(f"录音过程中出现异常：{self._callback_error}")

        path = self._path
        self._path = None
        if path is None:
            raise RuntimeError("临时录音文件丢失。")
        return path

    def cancel(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
        self._close_wave()
        self._delete_temporary_path()

    def _close_wave(self) -> None:
        if self._wave_file is not None:
            try:
                self._wave_file.close()
            finally:
                self._wave_file = None

    def _delete_temporary_path(self) -> None:
        if self._path is not None:
            self._path.unlink(missing_ok=True)
            self._path = None
