from __future__ import annotations

import importlib
import importlib.util
import os
import shutil
import sys
import threading
import types
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
_FUNASR_CLASSES: tuple[Any, Any, Any] | None = None


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


def check_models(config: AppConfig, require_punc: bool = True) -> list[str]:
    paths = resolve_model_paths(config)
    missing = []
    required = [("ASR", paths.asr), ("VAD", paths.vad)]
    if require_punc:
        required.append(("PUNC", paths.punc))
    for label, path in required:
        if not path.exists():
            missing.append(f"{label}: {path}")
    return missing


def copy_cached_models(dest_root: Path | None = None) -> Path:
    src = DEFAULT_VOCOTYPE_MODEL_ROOT
    if dest_root is None:
        dest_root = project_root() / ".local_models" / "iic"
    dest_root.mkdir(parents=True, exist_ok=True)

    for name in [ASR_MODEL, VAD_MODEL, PUNC_MODEL]:
        dest_dir = dest_root / name
        if dest_dir.exists():
            continue
        src_dir = src / name
        if src_dir.exists():
            shutil.copytree(src_dir, dest_dir)
            continue

        try:
            from modelscope import snapshot_download
        except ImportError as exc:
            raise RuntimeError(
                "本机没有模型缓存，也缺少 modelscope 下载工具。请重新运行 install.ps1。"
            ) from exc

        temp_dir = dest_root / f".{name}.download"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        try:
            snapshot_download(
                model_id=f"iic/{name}",
                local_dir=str(temp_dir),
            )
            if not temp_dir.exists():
                raise RuntimeError("下载完成后没有找到模型目录。")
            os.replace(temp_dir, dest_dir)
        except Exception as exc:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise RuntimeError(
                f"模型 {name} 下载失败，请检查网络后重试：{exc}"
            ) from exc
    return dest_root


def should_use_local_punctuation(config: AppConfig) -> bool:
    if not getattr(config, "skip_local_punctuation_when_ai_polish", True):
        return True
    if not config.enable_ai_polish:
        return True
    return config.output_mode in {"raw", "normalized"}


def _load_funasr_classes() -> tuple[Any, Any, Any]:
    """只加载项目使用的 ONNX 类，避开 funasr-onnx 对 torch 的非必要导入。"""
    global _FUNASR_CLASSES
    if _FUNASR_CLASSES is not None:
        return _FUNASR_CLASSES

    spec = importlib.util.find_spec("funasr_onnx")
    if spec is None or not spec.submodule_search_locations:
        raise ImportError("找不到 funasr-onnx")

    existing = sys.modules.get("funasr_onnx")
    if existing is None or not hasattr(existing, "__path__"):
        package = types.ModuleType("funasr_onnx")
        package.__file__ = spec.origin
        package.__package__ = "funasr_onnx"
        package.__path__ = list(spec.submodule_search_locations)
        package.__spec__ = spec
        sys.modules["funasr_onnx"] = package

    paraformer_module = importlib.import_module("funasr_onnx.paraformer_bin")
    vad_module = importlib.import_module("funasr_onnx.vad_bin")
    punc_module = importlib.import_module("funasr_onnx.punc_bin")
    _FUNASR_CLASSES = (
        vad_module.Fsmn_vad,
        paraformer_module.Paraformer,
        punc_module.CT_Transformer,
    )
    return _FUNASR_CLASSES


def get_engines(config: AppConfig, load_punc: bool = True) -> tuple[Any, Any, Any | None]:
    missing = check_models(config, require_punc=load_punc)
    if missing:
        raise FileNotFoundError("Model folders are incomplete:\n" + "\n".join(missing))

    paths = resolve_model_paths(config)
    cache_key = str(paths.root.resolve())
    with _ENGINE_LOCK:
        if _ENGINE_CACHE.get("key") != cache_key:
            _ENGINE_CACHE.clear()
            _ENGINE_CACHE["key"] = cache_key

        vad = _ENGINE_CACHE.get("vad")
        asr = _ENGINE_CACHE.get("asr")
        if vad is None or asr is None:
            try:
                Fsmn_vad, Paraformer, _CT_Transformer = _load_funasr_classes()
            except ImportError as exc:
                raise RuntimeError("缺少 funasr-onnx，请重新运行 install.ps1。") from exc

            vad = Fsmn_vad(model_dir=str(paths.vad), quantize=True)
            asr = Paraformer(model_dir=str(paths.asr), quantize=True)
            _ENGINE_CACHE.update({"vad": vad, "asr": asr})

        if load_punc and _ENGINE_CACHE.get("punc") is None:
            try:
                _Fsmn_vad, _Paraformer, CT_Transformer = _load_funasr_classes()
            except ImportError as exc:
                raise RuntimeError("缺少 funasr-onnx，请重新运行 install.ps1。") from exc

            _ENGINE_CACHE["punc"] = CT_Transformer(model_dir=str(paths.punc), quantize=True)

        return vad, asr, _ENGINE_CACHE.get("punc")


def warmup_models(config: AppConfig) -> None:
    get_engines(config, load_punc=should_use_local_punctuation(config))


def transcribe_audio(audio_path: Path, config: AppConfig, use_local_punctuation: bool | None = None) -> str:
    use_punc = should_use_local_punctuation(config) if use_local_punctuation is None else use_local_punctuation
    _vad, asr, punc = get_engines(config, load_punc=use_punc)
    raw_result: Any = asr(str(audio_path))
    raw_text = extract_text(raw_result)
    if not raw_text:
        return ""
    if not use_punc or punc is None:
        return raw_text.strip()
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
