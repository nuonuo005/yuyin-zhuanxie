from __future__ import annotations

import unittest
from unittest.mock import patch

from yuyin_zhuanxie.config import AppConfig
from yuyin_zhuanxie.gui_modern import ModernTranscriberApp


class _DummyApp:
    def __init__(self) -> None:
        self.config_data = AppConfig(
            copy_result_to_clipboard=False,
            auto_paste=True,
            enable_ai_polish=False,
            save_history=False,
            filter_filler_words=False,
        )
        self.events: list[tuple] = []

    def after(self, delay, callback) -> None:
        self.events.append(("after", delay))
        callback()

    def send_paste(self) -> None:
        self.events.append(("paste",))

    def fill_outputs(self, *_args) -> None:
        self.events.append(("fill",))

    def set_runtime_state(self, text: str) -> None:
        self.events.append(("status", text))

    def _sync_float_visibility(self) -> None:
        self.events.append(("float",))


class GuiProcessingTests(unittest.TestCase):
    def test_failed_clipboard_write_does_not_paste(self) -> None:
        app = _DummyApp()
        with patch("yuyin_zhuanxie.gui_modern.write_clipboard", return_value=False):
            ModernTranscriberApp._process_text_worker(app, "RAW", "test", None)
        self.assertFalse(any(event[0] == "paste" for event in app.events))
        self.assertTrue(
            any(
                event[0] == "status" and "剪贴板失败" in event[1]
                for event in app.events
            )
        )


if __name__ == "__main__":
    unittest.main()
