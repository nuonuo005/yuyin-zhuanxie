from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .secrets import protect_secret, unprotect_secret


DEFAULT_SYSTEM_PROMPT = (
    "你是一个中文口语整理助手。请严格保留用户原意，不新增事实，不改变人称。"
    "把口语化、重复、停顿和错别字整理成自然、准确、可直接发送的书面中文。只输出最终文本。"
)

DEFAULT_PROVIDERS = [
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-v4-flash",
        "api_key": "",
    },
    {
        "id": "openai_compatible",
        "name": "OpenAI Compatible",
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "qwen2.5:7b",
        "api_key": "",
    },
]

DEFAULT_PROMPTS = [
    {
        "id": "formal",
        "name": "书面整理",
        "tag": "内置",
        "hotkey": "",
        "prompt": DEFAULT_SYSTEM_PROMPT,
    },
    {
        "id": "meeting",
        "name": "会议纪要",
        "tag": "内置",
        "hotkey": "",
        "prompt": (
            "你是会议纪要整理助手。把口语转写整理为清晰的会议纪要，包含背景、结论、待办和风险。"
            "不要新增原文没有的信息。"
        ),
    },
    {
        "id": "message",
        "name": "消息回复",
        "tag": "内置",
        "hotkey": "",
        "prompt": (
            "你是中文消息润色助手。把用户的口语表达整理成礼貌、自然、简洁、可直接发送的消息。"
            "保留原意，不改变人称。"
        ),
    },
]

DEFAULT_REPLACEMENTS = [
    {"from": "f二", "to": "F2", "enabled": True},
    {"from": "回车", "to": "Enter", "enabled": False},
]


@dataclass
class AppConfig:
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-v4-flash"
    model_root: str = ".local_models/iic"
    copy_result_to_clipboard: bool = True
    save_history: bool = True
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    ai_provider: str = "deepseek"
    active_prompt_id: str = "formal"
    hotkey: str = "F2"
    hold_to_record: bool = True
    show_floating_indicator: bool = True
    auto_paste: bool = True
    start_minimized: bool = False
    smart_numbers: bool = False
    filter_filler_words: bool = True
    strip_trailing_punctuation: bool = False
    keep_raw_clipboard: bool = False
    enable_ai_polish: bool = True
    skip_local_punctuation_when_ai_polish: bool = True
    ai_timeout_seconds: int = 60
    ai_max_tokens: int = 4000
    max_recording_seconds: int = 600
    history_max_entries: int = 5000
    output_mode: str = "polished"
    float_x: int | None = None
    float_y: int | None = None
    float_size: str = "medium"
    float_style: str = "minimal"
    providers: list[dict] = field(default_factory=list)
    prompts: list[dict] = field(default_factory=list)
    replacement_rules: list[dict] = field(default_factory=list)
    glossary: list[str] = field(default_factory=list)


_CONFIG_WARNING = ""


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def config_path() -> Path:
    return project_root() / "config.json"


def config_backup_path() -> Path:
    return project_root() / "config.json.bak"


def get_config_warning() -> str:
    return _CONFIG_WARNING


def _read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("配置文件最外层必须是 JSON 对象。")
    return data


def _load_raw_config() -> dict:
    global _CONFIG_WARNING
    _CONFIG_WARNING = ""
    path = config_path()
    backup = config_backup_path()
    if not path.exists():
        return {}

    try:
        return _read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as primary_exc:
        if backup.exists():
            try:
                data = _read_json(backup)
                _CONFIG_WARNING = (
                    f"主配置文件读取失败，已使用备份配置。原因：{primary_exc}"
                )
                return data
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        _CONFIG_WARNING = (
            f"配置文件读取失败，程序已使用安全默认设置。原文件未删除。原因：{primary_exc}"
        )
        return {}


def _decrypt_config_secrets(data: dict) -> None:
    global _CONFIG_WARNING
    encrypted = data.get("deepseek_api_key", "")
    if isinstance(encrypted, str):
        try:
            data["deepseek_api_key"] = unprotect_secret(encrypted)
        except (OSError, ValueError) as exc:
            data["deepseek_api_key"] = ""
            _CONFIG_WARNING = f"{_CONFIG_WARNING}\n{exc}".strip()

    providers = data.get("providers")
    if not isinstance(providers, list):
        return
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        value = provider.get("api_key", "")
        if not isinstance(value, str):
            provider["api_key"] = ""
            continue
        try:
            provider["api_key"] = unprotect_secret(value)
        except (OSError, ValueError) as exc:
            provider["api_key"] = ""
            _CONFIG_WARNING = f"{_CONFIG_WARNING}\n{exc}".strip()


def _sanitize_config_data(data: dict) -> dict:
    defaults = AppConfig()
    clean: dict = {}
    bool_fields = {
        "copy_result_to_clipboard",
        "save_history",
        "hold_to_record",
        "show_floating_indicator",
        "auto_paste",
        "start_minimized",
        "smart_numbers",
        "filter_filler_words",
        "strip_trailing_punctuation",
        "keep_raw_clipboard",
        "enable_ai_polish",
        "skip_local_punctuation_when_ai_polish",
    }
    int_fields = {
        "ai_timeout_seconds",
        "ai_max_tokens",
        "max_recording_seconds",
        "history_max_entries",
    }
    nullable_int_fields = {"float_x", "float_y"}
    list_fields = {"providers", "prompts", "replacement_rules", "glossary"}

    for key in AppConfig.__annotations__:
        if key not in data:
            continue
        value = data[key]
        if key in bool_fields and isinstance(value, bool):
            clean[key] = value
        elif key in int_fields and isinstance(value, int) and value > 0:
            clean[key] = value
        elif key in nullable_int_fields and (value is None or isinstance(value, int)):
            clean[key] = value
        elif key in list_fields and isinstance(value, list):
            clean[key] = value
        elif key not in bool_fields | int_fields | nullable_int_fields | list_fields and isinstance(value, str):
            clean[key] = value

    clean["ai_timeout_seconds"] = max(10, min(int(clean.get("ai_timeout_seconds", defaults.ai_timeout_seconds)), 300))
    clean["ai_max_tokens"] = max(600, min(int(clean.get("ai_max_tokens", defaults.ai_max_tokens)), 32000))
    clean["max_recording_seconds"] = max(
        30,
        min(int(clean.get("max_recording_seconds", defaults.max_recording_seconds)), 7200),
    )
    clean["history_max_entries"] = max(
        100,
        min(int(clean.get("history_max_entries", defaults.history_max_entries)), 50000),
    )
    return clean


def load_config() -> AppConfig:
    data = _load_raw_config()
    _decrypt_config_secrets(data)

    allowed = _sanitize_config_data(data)
    config = AppConfig(**allowed)
    if not config.providers:
        config.providers = [dict(provider) for provider in DEFAULT_PROVIDERS]
        config.providers[0]["base_url"] = data.get("deepseek_base_url", config.deepseek_base_url)
        config.providers[0]["model"] = data.get("deepseek_model", config.deepseek_model)
        config.providers[0]["api_key"] = data.get("deepseek_api_key", config.deepseek_api_key)
    if not config.prompts:
        config.prompts = [dict(prompt) for prompt in DEFAULT_PROMPTS]
        config.prompts[0]["prompt"] = data.get("system_prompt", config.system_prompt)
    if not config.replacement_rules:
        config.replacement_rules = [dict(rule) for rule in DEFAULT_REPLACEMENTS]

    for provider in config.providers:
        base_url = str(provider.get("base_url", ""))
        model = str(provider.get("model", ""))
        if "api.deepseek.com" in base_url and model in {"deepseek-chat", "deepseek-reasoner"}:
            provider["model"] = "deepseek-v4-flash"
    if (
        "api.deepseek.com" in config.deepseek_base_url
        and config.deepseek_model in {"deepseek-chat", "deepseek-reasoner"}
    ):
        config.deepseek_model = "deepseek-v4-flash"

    sync_legacy_fields(config)
    env_key = os.getenv("DEEPSEEK_API_KEY")
    if env_key:
        config.deepseek_api_key = env_key
    return config


def save_config(config: AppConfig) -> None:
    data = {key: getattr(config, key) for key in AppConfig.__annotations__}
    data["deepseek_api_key"] = protect_secret(str(data.get("deepseek_api_key", "")))
    providers = []
    for provider in config.providers:
        item = dict(provider)
        item["api_key"] = protect_secret(str(item.get("api_key", "")))
        providers.append(item)
    data["providers"] = providers

    path = config_path()
    backup = config_backup_path()
    temp = path.with_suffix(".json.tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2)
    temp.write_text(text, encoding="utf-8")
    _read_json(temp)
    os.replace(temp, path)
    shutil.copy2(path, backup)


def get_active_provider(config: AppConfig) -> dict | None:
    for provider in config.providers:
        if provider.get("id") == config.ai_provider:
            return provider
    return config.providers[0] if config.providers else None


def get_active_prompt(config: AppConfig) -> dict | None:
    for prompt in config.prompts:
        if prompt.get("id") == config.active_prompt_id:
            return prompt
    return config.prompts[0] if config.prompts else None


def sync_legacy_fields(config: AppConfig) -> None:
    provider = get_active_provider(config)
    if provider:
        config.deepseek_base_url = provider.get("base_url", config.deepseek_base_url)
        config.deepseek_model = provider.get("model", config.deepseek_model)
        config.deepseek_api_key = provider.get("api_key", config.deepseek_api_key)

    prompt = get_active_prompt(config)
    if prompt:
        config.system_prompt = prompt.get("prompt", config.system_prompt)


def sync_provider_from_legacy(config: AppConfig) -> None:
    provider = get_active_provider(config)
    if not provider:
        return
    provider["base_url"] = config.deepseek_base_url
    provider["model"] = config.deepseek_model
    provider["api_key"] = config.deepseek_api_key


def sync_prompt_from_legacy(config: AppConfig) -> None:
    prompt = get_active_prompt(config)
    if prompt:
        prompt["prompt"] = config.system_prompt
