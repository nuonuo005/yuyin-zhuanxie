from __future__ import annotations

import os
from pathlib import Path

from .config import project_root


APP_NAME = "语言转写"


def startup_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def startup_file() -> Path:
    return startup_dir() / f"{APP_NAME}.bat"


def is_enabled() -> bool:
    return startup_file().exists()


def set_enabled(enabled: bool) -> None:
    path = startup_file()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        launcher = project_root() / "YuyanZhuanxie.vbs"
        path.write_text(f'@echo off\nwscript.exe "{launcher}"\n', encoding="utf-8")
    elif path.exists():
        path.unlink()
