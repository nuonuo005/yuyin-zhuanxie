from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from yuyin_zhuanxie.config import AppConfig, get_config_warning, load_config, save_config


class ConfigTests(unittest.TestCase):
    def test_secret_is_encrypted_and_roundtrips(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = AppConfig(
                deepseek_api_key="secret-value",
                ai_provider="p1",
                providers=[
                    {
                        "id": "p1",
                        "name": "Test",
                        "base_url": "https://example.com/v1",
                        "model": "model",
                        "api_key": "provider-secret",
                    }
                ],
            )
            with patch("yuyin_zhuanxie.config.project_root", return_value=root):
                save_config(config)
                text = (root / "config.json").read_text(encoding="utf-8")
                self.assertNotIn("provider-secret", text)
                self.assertIn("dpapi:", text)
                loaded = load_config()
                self.assertEqual(loaded.providers[0]["api_key"], "provider-secret")

    def test_corrupt_primary_uses_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("yuyin_zhuanxie.config.project_root", return_value=root):
                save_config(AppConfig(hotkey="F8"))
                (root / "config.json").write_text("{broken", encoding="utf-8")
                loaded = load_config()
                self.assertEqual(loaded.hotkey, "F8")
                self.assertIn("备份配置", get_config_warning())


if __name__ == "__main__":
    unittest.main()
