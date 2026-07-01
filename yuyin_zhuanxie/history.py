from __future__ import annotations

import json
from datetime import datetime

from .config import project_root


def append_history(raw_text: str, polished_text: str, source: str) -> None:
    path = project_root() / "history.jsonl"
    record = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "raw_text": raw_text,
        "polished_text": polished_text,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
