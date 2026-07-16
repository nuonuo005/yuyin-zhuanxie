from __future__ import annotations

import re

from .config import AppConfig


CN_NUM = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNIT = {"十": 10, "百": 100, "千": 1000, "万": 10000}
NON_NUMERIC_NUMBER_WORDS = {"万一", "千万"}

FILLER_PATTERNS = [
    r"嗯+",
    r"呃+",
    r"啊+",
    r"这个",
    r"那个",
    r"就是",
    r"然后",
]


def normalize_text(text: str, config: AppConfig) -> str:
    result = text.strip()
    for rule in config.replacement_rules:
        if not rule.get("enabled", True):
            continue
        src = str(rule.get("from", ""))
        dst = str(rule.get("to", ""))
        if src:
            result = result.replace(src, dst)

    if config.filter_filler_words:
        for pattern in FILLER_PATTERNS:
            result = re.sub(pattern, "", result)
        result = re.sub(r"\s+", " ", result).strip()

    if config.smart_numbers:
        result = convert_chinese_numbers(result)

    if config.strip_trailing_punctuation:
        result = re.sub(r"[。！？!?；;，,、\s]+$", "", result)

    return result


def choose_output(raw_text: str, normalized_text: str, polished_text: str, config: AppConfig) -> str:
    if config.output_mode == "raw":
        return raw_text
    if config.output_mode == "normalized":
        return normalized_text
    return polished_text or normalized_text or raw_text


def convert_chinese_numbers(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        token = match.group(0)
        if len(token) == 1 or token in NON_NUMERIC_NUMBER_WORDS:
            return token
        value = chinese_number_to_int(token)
        return str(value) if value is not None else token

    return re.sub(r"[零一二两三四五六七八九十百千万]+", repl, text)


def chinese_number_to_int(token: str) -> int | None:
    if not token:
        return None
    if all(ch in CN_NUM for ch in token):
        return int("".join(str(CN_NUM[ch]) for ch in token))

    total = 0
    section = 0
    number = 0
    used_unit = False
    for ch in token:
        if ch in CN_NUM:
            number = CN_NUM[ch]
        elif ch in CN_UNIT:
            used_unit = True
            unit = CN_UNIT[ch]
            if unit == 10000:
                section = (section + number) * unit
                total += section
                section = 0
            else:
                section += (number or 1) * unit
            number = 0
        else:
            return None
    if not used_unit:
        return None
    return total + section + number
