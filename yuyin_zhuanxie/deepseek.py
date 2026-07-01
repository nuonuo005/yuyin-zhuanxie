from __future__ import annotations

import requests

from .config import AppConfig, get_active_provider, get_active_prompt


class DeepSeekError(RuntimeError):
    pass


def polish_text(text: str, config: AppConfig, prompt_id: str | None = None) -> str:
    if not text.strip():
        raise DeepSeekError("没有可处理的文本。")

    provider = get_active_provider(config)
    if not provider:
        raise DeepSeekError("没有可用的 AI 供应商配置。")

    api_key = provider.get("api_key") or config.deepseek_api_key
    base_url = provider.get("base_url") or config.deepseek_base_url
    model = provider.get("model") or config.deepseek_model

    # 优先使用传入的 prompt_id，否则使用全局默认
    if prompt_id:
        prompt = None
        for p in config.prompts:
            if p.get("id") == prompt_id:
                prompt = p
                break
    else:
        prompt = get_active_prompt(config)

    system_prompt = (prompt or {}).get("prompt") or config.system_prompt

    if not api_key and not base_url.startswith("http://127.0.0.1") and not base_url.startswith("http://localhost"):
        raise DeepSeekError("缺少 API Key。请在 AI 供应商里填写，或设置 DEEPSEEK_API_KEY。")

    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": 0.3,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    response = requests.post(url, json=payload, headers=headers, timeout=60)
    if response.status_code >= 400:
        raise DeepSeekError(f"AI 请求失败：HTTP {response.status_code} {response.text[:500]}")

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise DeepSeekError(f"AI 返回格式异常：{data}") from exc
