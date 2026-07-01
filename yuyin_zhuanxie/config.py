from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_SYSTEM_PROMPT = (
    "你是一个中文口语整理助手。请严格保留用户原意，不新增事实，不改变人称。"
    "把口语化、重复、停顿和错别字整理成自然、准确、可直接发送的书面中文。只输出最终文本。"
)

DEFAULT_PROVIDERS = [
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
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
        "prompt": DEFAULT_SYSTEM_PROMPT,
    },
    {
        "id": "meeting",
        "name": "会议纪要",
        "tag": "内置",
        "prompt": (
            "你是会议纪要整理助手。把口语转写整理为清晰的会议纪要，包含背景、结论、待办和风险。"
            "不要新增原文没有的信息。"
        ),
    },
    {
        "id": "message",
        "name": "消息回复",
        "tag": "内置",
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
    deepseek_model: str = "deepseek-chat"
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
    output_mode: str = "polished"
    providers: list[dict] = field(default_factory=list)
    prompts: list[dict] = field(default_factory=list)
    replacement_rules: list[dict] = field(default_factory=list)
    glossary: list[str] = field(default_factory=list)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def config_path() -> Path:
    return project_root() / "config.json"


def load_config() -> AppConfig:
    path = config_path()
    data: dict = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))

    allowed = {k: v for k, v in data.items() if k in AppConfig.__annotations__}
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

    sync_legacy_fields(config)
    env_key = os.getenv("DEEPSEEK_API_KEY")
    if env_key:
        config.deepseek_api_key = env_key
    return config


def save_config(config: AppConfig) -> None:
    data = {key: getattr(config, key) for key in AppConfig.__annotations__}
    config_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
