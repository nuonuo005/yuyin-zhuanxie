from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

from .config import project_root


_HISTORY_LOCK = threading.Lock()
_HISTORY_COUNT: int | None = None


def append_history(
    raw_text: str,
    polished_text: str,
    source: str,
    max_entries: int = 5000,
) -> None:
    global _HISTORY_COUNT
    path = project_root() / "history.jsonl"
    record = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "raw_text": raw_text,
        "polished_text": polished_text,
    }
    with _HISTORY_LOCK:
        if _HISTORY_COUNT is None:
            if path.exists():
                with path.open("r", encoding="utf-8") as existing:
                    _HISTORY_COUNT = sum(1 for _ in existing)
            else:
                _HISTORY_COUNT = 0
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        _HISTORY_COUNT += 1
        if _HISTORY_COUNT > max_entries:
            trim_history(path, max_entries=max_entries)
            _HISTORY_COUNT = min(_HISTORY_COUNT, max_entries)


def trim_history(path: Path, max_entries: int = 5000) -> None:
    max_entries = max(100, int(max_entries))
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) <= max_entries:
        return
    temp = path.with_suffix(".jsonl.tmp")
    temp.write_text("\n".join(lines[-max_entries:]) + "\n", encoding="utf-8")
    os.replace(temp, path)
