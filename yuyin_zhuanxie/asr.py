from __future__ import annotations

import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AppConfig, project_root


DEFAULT_VOCOTYPE_MODEL_ROOT = Path.home() / ".cache" / "modelscope" / "hub" / "models" / "iic"

ASR_MODEL = "speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-onnx"
VAD_MODEL = "speech_fsmn_vad_zh-cn-16k-common-onnx"
PUNC_MODEL = "punc_ct-transformer_zh-cn-common-vocab272727-onnx"

_ENGINE_LOCK = threading.Lock()
_ENGINE_CACHE: dict[str, Any] = {}


@dataclass
class ModelPaths:
    root: Path
    asr: Path
    vad: Path
    punc: Path


def resolve_model_paths(config: AppConfig) -> ModelPaths:
    root = Path(config.model_root)
    if not root.is_absolute():
        root = project_root() / root

    if not root.exists() and DEFAULT_VOCOTYPE_MODEL_ROOT.exists():
        root = DEFAULT_VOCOTYPE_MODEL_ROOT

    return ModelPaths(root=root, asr=root / ASR_MODEL, vad=root / VAD_MODEL, punc=root / PUNC_MODEL)


def check_models(config: AppConfig) -> list[str]:
    paths = resolve_model_paths(config)
    missing = []
    for label, path in [("ASR", paths.asr), ("VAD", paths.vad), ("PUNC", paths.punc)]:
        if not path.exists():
            missing.append(f"{label}: {path}")
    return missing


def copy_cached_models(dest_root: Path | None = None) -> Path:
    src = DEFAULT_VOCOTYPE_MODEL_ROOT
    if not src.exists():
        raise FileNotFoundError(f"没有找到本机 ModelScope 缓存目录：{src}")

    if dest_root is None:
        dest_root = project_root() / ".local_models" / "iic"
    dest_root.mkdir(parents=True, exist_ok=True)

    for name in [ASR_MODEL, VAD_MODEL, PUNC_MODEL]:
        src_dir = src / name
        dest_dir = dest_root / name
        if not src_dir.exists():
            raise FileNotFoundError(f"模型目录不存在：{src_dir}")
        if dest_dir.exists():
            continue
        shutil.copytree(src_dir, dest_dir)
    return dest_root


def get_engines(config: AppConfig) -> tuple[Any, Any, Any]:
    missing = check_models(config)
    if missing:
        raise FileNotFoundError("模型目录不完整：\n" + "\n".join(missing))

    paths = resolve_model_paths(config)
    cache_key = str(paths.root.resolve())
    with _ENGINE_LOCK:
        if _ENGINE_CACHE.get("key") == cache_key:
            return _ENGINE_CACHE["vad"], _ENGINE_CACHE["asr"], _ENGINE_CACHE["punc"]

        try:
            from funasr_onnx import CT_Transformer, Fsmn_vad, Paraformer
        except ImportError as exc:
            raise RuntimeError("缺少 funasr-onnx。请运行 install.ps1 重新安装依赖。") from exc

        vad = Fsmn_vad(model_dir=str(paths.vad), quantize=True)
        asr = Paraformer(model_dir=str(paths.asr), quantize=True)
        punc = CT_Transformer(model_dir=str(paths.punc), quantize=True)
        _ENGINE_CACHE.clear()
        _ENGINE_CACHE.update({"key": cache_key, "vad": vad, "asr": asr, "punc": punc})
        return vad, asr, punc


def warmup_models(config: AppConfig) -> None:
    get_engines(config)


def transcribe_audio(audio_path: Path, config: AppConfig) -> str:
    _vad, asr, punc = get_engines(config)
    raw_result: Any = asr(str(audio_path))
    raw_text = extract_text(raw_result)
    if not raw_text:
        return ""
    punc_result = punc(raw_text)
    if isinstance(punc_result, tuple):
        return str(punc_result[0]).strip()
    return str(punc_result).strip()


def extract_text(result: Any) -> str:
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, tuple):
        return extract_text(result[0]) if result else ""
    if isinstance(result, dict):
        text = result.get("text") or result.get("sentence") or result.get("preds")
        return extract_text(text) if text is not None else ""
    if isinstance(result, list):
        parts = []
        for item in result:
            if isinstance(item, dict):
                text = item.get("text") or item.get("sentence") or item.get("preds")
                if text:
                    parts.append(extract_text(text))
            elif isinstance(item, str):
                parts.append(item)
            elif isinstance(item, tuple):
                parts.append(extract_text(item))
        return "".join(parts).strip()
    return str(result).strip()
