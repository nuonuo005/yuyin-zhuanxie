from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yuyin_zhuanxie.history as history


class HistoryTests(unittest.TestCase):
    def test_history_is_limited_by_entry_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("yuyin_zhuanxie.history.project_root", return_value=root):
                history._HISTORY_COUNT = None
                for index in range(105):
                    history.append_history(
                        f"raw-{index}",
                        f"output-{index}",
                        "test",
                        max_entries=100,
                    )
                lines = (root / "history.jsonl").read_text(encoding="utf-8").splitlines()
                self.assertEqual(len(lines), 100)
                self.assertIn("raw-5", lines[0])


if __name__ == "__main__":
    unittest.main()
