from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from .asr import copy_cached_models, resolve_model_paths, transcribe_audio
from .clipboard import read_clipboard, write_clipboard
from .config import load_config, project_root
from .deepseek import polish_text
from .history import append_history
from .text_tools import choose_output, normalize_text


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="语言转写", description="本地语音转写 + AI 书面化")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("gui", help="打开可视化客户端")
    sub.add_parser("doctor", help="检查环境、模型路径和依赖")
    sub.add_parser("init-models", help="准备本地模型：优先复制缓存，缺失时从 ModelScope 下载")
    sub.add_parser("polish-clipboard", help="读取剪贴板文本，AI 书面化后写回剪贴板")

    p_transcribe = sub.add_parser("transcribe", help="使用本地模型转写音频文件")
    p_transcribe.add_argument("audio", help="音频文件路径")

    p_run = sub.add_parser("run", help="转写音频文件，AI 书面化后写入剪贴板")
    p_run.add_argument("audio", help="音频文件路径")

    args = parser.parse_args(argv)
    config = load_config()

    try:
        if args.command == "gui":
            from .gui_modern import run_modern_gui

            run_modern_gui()
        elif args.command == "doctor":
            cmd_doctor(config)
        elif args.command == "init-models":
            dest = copy_cached_models()
            print(f"模型已准备好：{dest}")
        elif args.command == "polish-clipboard":
            raw = read_clipboard()
            normalized = normalize_text(raw, config)
            polished = polish_text(normalized, config)
            output = choose_output(raw, normalized, polished, config)
            if not write_clipboard(output):
                raise RuntimeError("无法写入剪贴板，请稍后重试。")
            if config.save_history:
                append_history(
                    raw,
                    output,
                    "clipboard",
                    max_entries=config.history_max_entries,
                )
            print(output)
            print("\n已写入剪贴板。")
        elif args.command == "transcribe":
            audio = Path(args.audio).expanduser().resolve()
            text = transcribe_audio(audio, config, use_local_punctuation=True)
            print(text)
        elif args.command == "run":
            audio = Path(args.audio).expanduser().resolve()
            raw = transcribe_audio(audio, config)
            normalized = normalize_text(raw, config)
            polished = polish_text(normalized, config)
            output = choose_output(raw, normalized, polished, config)
            if config.copy_result_to_clipboard:
                if not write_clipboard(output):
                    raise RuntimeError("无法写入剪贴板，请稍后重试。")
            if config.save_history:
                append_history(
                    raw,
                    output,
                    str(audio),
                    max_entries=config.history_max_entries,
                )
            print(output)
            if config.copy_result_to_clipboard:
                print("\n已写入剪贴板。")
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def cmd_doctor(config) -> None:
    print(f"项目目录：{project_root()}")
    paths = resolve_model_paths(config)
    print(f"模型根目录：{paths.root}")
    for label, path in [("ASR", paths.asr), ("VAD", paths.vad), ("PUNC", paths.punc)]:
        mark = "OK" if path.exists() else "MISSING"
        print(f"{mark} {label}: {path}")

    for package in [
        "funasr_onnx",
        "modelscope",
        "onnxruntime",
        "numpy",
        "requests",
        "sounddevice",
        "keyboard",
        "customtkinter",
        "pystray",
        "PIL",
    ]:
        mark = "OK" if importlib.util.find_spec(package) else "MISSING"
        print(f"{mark} Python package: {package}")

    key_state = "OK" if config.deepseek_api_key else "MISSING"
    print(f"{key_state} AI API Key")


if __name__ == "__main__":
    main()
