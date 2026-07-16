from __future__ import annotations

from urllib.parse import urlparse

import requests

from .config import AppConfig, get_active_provider, get_active_prompt


class DeepSeekError(RuntimeError):
    pass


def build_chat_url(base_url: str) -> str:
    base_url = str(base_url or "").strip()
    if not base_url:
        raise DeepSeekError("AI 接口地址为空，请填写 Base URL。")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise DeepSeekError("AI 接口地址格式不正确，必须以 http:// 或 https:// 开头。")

    url = base_url.rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    return url + "/chat/completions"


def validate_provider(base_url: str, model: str) -> None:
    build_chat_url(base_url)
    if not str(model or "").strip():
        raise DeepSeekError("模型名为空，请填写模型名。")


def polish_text(text: str, config: AppConfig, prompt_id: str | None = None) -> str:
    if not text.strip():
        raise DeepSeekError("没有可处理的文本。")

    provider = get_active_provider(config)
    if not provider:
        raise DeepSeekError("没有可用的 AI 供应商配置。")

    api_key = str(provider.get("api_key") or config.deepseek_api_key or "").strip()
    base_url = str(provider.get("base_url") or config.deepseek_base_url or "").strip()
    model = str(provider.get("model") or config.deepseek_model or "").strip()
    validate_provider(base_url, model)

    # 优先使用传入的 prompt_id，否则使用全局默认
    if prompt_id:
        prompt = None
        for p in config.prompts:
            if p.get("id") == prompt_id:
                prompt = p
                break
    else:
        prompt = get_active_prompt(config)

    PLACEHOLDER = "{{这里放入语音转文字后的原始文本}}"
    system_prompt = (prompt or {}).get("prompt") or config.system_prompt

    if not api_key and not base_url.startswith("http://127.0.0.1") and not base_url.startswith("http://localhost"):
        raise DeepSeekError("缺少 API Key。请在 AI 供应商里填写，或设置 DEEPSEEK_API_KEY。")

    # 构建消息：如果提示词包含占位符，替换后只发 system；否则 system + user 分离发送
    url = build_chat_url(base_url)
    if PLACEHOLDER in system_prompt:
        system_prompt = system_prompt.replace(PLACEHOLDER, text)
        messages = [{"role": "system", "content": system_prompt}]
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]

    max_tokens = min(
        max(600, len(text) * 2),
        max(600, int(getattr(config, "ai_max_tokens", 4000))),
    )
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    timeout_seconds = max(10, int(getattr(config, "ai_timeout_seconds", 60)))
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=(8, timeout_seconds),
        )
    except requests.Timeout as exc:
        raise DeepSeekError(f"AI 请求超时（等待超过 {timeout_seconds} 秒），请检查网络后重试。") from exc
    except requests.ConnectionError as exc:
        raise DeepSeekError("无法连接 AI 接口，请检查网络、Base URL 或本地模型服务是否启动。") from exc
    except requests.RequestException as exc:
        raise DeepSeekError(f"AI 请求失败：{exc}") from exc

    if response.status_code >= 400:
        if response.status_code == 401:
            raise DeepSeekError("AI 接口拒绝访问（401），请检查 API Key。")
        if response.status_code == 429:
            raise DeepSeekError("AI 请求过于频繁或余额不足（429），请稍后重试并检查账户额度。")
        raise DeepSeekError(f"AI 请求失败：HTTP {response.status_code} {response.text[:300]}")

    try:
        data = response.json()
    except requests.JSONDecodeError as exc:
        raise DeepSeekError(f"AI 返回的不是有效 JSON：{response.text[:300]}") from exc

    try:
        choice = data["choices"][0]
        content = choice["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise DeepSeekError(f"AI 返回格式异常：{str(data)[:500]}") from exc
    if not content:
        raise DeepSeekError("AI 返回了空内容。")
    if choice.get("finish_reason") == "length":
        raise DeepSeekError("AI 输出达到长度上限，结果可能被截断。已保留完整的本地整理文本。")
    return content
