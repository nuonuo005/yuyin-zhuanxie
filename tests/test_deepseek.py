from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from yuyin_zhuanxie.config import AppConfig
from yuyin_zhuanxie.deepseek import DeepSeekError, build_chat_url, polish_text


class _Handler(BaseHTTPRequestHandler):
    response_status = 200
    response_data: dict = {
        "choices": [
            {
                "message": {"content": "MOCK_OK"},
                "finish_reason": "stop",
            }
        ]
    }
    captured: dict = {}

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.__class__.captured = {
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "body": json.loads(self.rfile.read(length)),
        }
        body = json.dumps(self.__class__.response_data).encode("utf-8")
        self.send_response(self.__class__.response_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        return


class DeepSeekTests(unittest.TestCase):
    def setUp(self) -> None:
        _Handler.response_status = 200
        _Handler.response_data = {
            "choices": [
                {
                    "message": {"content": "MOCK_OK"},
                    "finish_reason": "stop",
                }
            ]
        }
        self.server = HTTPServer(("127.0.0.1", 0), _Handler)

    def tearDown(self) -> None:
        self.server.server_close()

    def _config(self) -> AppConfig:
        return AppConfig(
            ai_provider="mock",
            active_prompt_id="p1",
            providers=[
                {
                    "id": "mock",
                    "base_url": f"http://127.0.0.1:{self.server.server_port}/v1",
                    "model": "mock-model",
                    "api_key": "audit",
                }
            ],
            prompts=[
                {
                    "id": "p1",
                    "prompt": "整理：{{这里放入语音转文字后的原始文本}}",
                }
            ],
        )

    def _serve_once(self) -> threading.Thread:
        thread = threading.Thread(target=self.server.handle_request)
        thread.start()
        return thread

    def test_build_chat_url_accepts_base_and_full_url(self) -> None:
        self.assertEqual(
            build_chat_url("https://api.deepseek.com/v1"),
            "https://api.deepseek.com/v1/chat/completions",
        )
        self.assertEqual(
            build_chat_url("https://example.com/v1/chat/completions"),
            "https://example.com/v1/chat/completions",
        )

    def test_request_and_placeholder_format(self) -> None:
        thread = self._serve_once()
        result = polish_text("INPUT_TEXT", self._config())
        thread.join(5)
        self.assertEqual(result, "MOCK_OK")
        self.assertEqual(_Handler.captured["path"], "/v1/chat/completions")
        self.assertTrue(_Handler.captured["authorization"].startswith("Bearer "))
        messages = _Handler.captured["body"]["messages"]
        self.assertEqual([item["role"] for item in messages], ["system"])
        self.assertIn("INPUT_TEXT", messages[0]["content"])

    def test_truncated_response_is_not_silently_used(self) -> None:
        _Handler.response_data = {
            "choices": [
                {
                    "message": {"content": "PARTIAL"},
                    "finish_reason": "length",
                }
            ]
        }
        thread = self._serve_once()
        with self.assertRaisesRegex(DeepSeekError, "截断"):
            polish_text("INPUT_TEXT", self._config())
        thread.join(5)


if __name__ == "__main__":
    unittest.main()
