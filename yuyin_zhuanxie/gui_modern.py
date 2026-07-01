from __future__ import annotations

import threading
import time
import uuid
import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import autostart
from .asr import copy_cached_models, resolve_model_paths, transcribe_audio, warmup_models
from .clipboard import read_clipboard, write_clipboard
from .config import get_active_prompt, get_active_provider, load_config, save_config
from .deepseek import polish_text
from .history import append_history
from .recorder import AudioRecorder
from .text_tools import choose_output, normalize_text
from .winfocus import get_foreground_window, is_own_window, paste_to_window


ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class ModernTranscriberApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("语言转写")
        self.geometry("1180x760")
        self.minsize(1040, 680)

        self.config_data = load_config()
        self.recorder = AudioRecorder()
        self.recording = False
        self.started_at = 0.0
        self.hotkey_error = ""
        self.current_page = ""
        self.float_window: tk.Toplevel | None = None
        self.float_label: tk.Label | None = None
        self.float_status = "模型加载中"
        self.target_hwnd = 0
        self.last_external_hwnd = 0
        self.own_pid = os.getpid()
        self.provider_index = 0
        self.prompt_index = 0
        self.rule_index = 0

        self.colors = {
            "bg": "#f4f7fb",
            "panel": "#ffffff",
            "soft": "#eef4ff",
            "line": "#dce5f2",
            "text": "#102033",
            "muted": "#66758a",
            "primary": "#2f6df6",
            "primary_hover": "#2358ca",
        }

        self._build_shell()
        self.show_home()
        self.register_hotkey()
        self.track_external_focus()
        self.preload_models_background()
        self.after(300, self.ensure_floating_button)
        if self.config_data.start_minimized:
            self.iconify()

    def _build_shell(self) -> None:
        self.configure(fg_color=self.colors["bg"])
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color="#edf2f8")
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(
            self.sidebar,
            text="语言转写",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=24, weight="bold"),
            text_color=self.colors["text"],
            anchor="w",
        ).pack(fill="x", padx=22, pady=(28, 4))
        ctk.CTkLabel(
            self.sidebar,
            text="本地识别 · AI 书面化",
            font=ctk.CTkFont(size=13),
            text_color=self.colors["muted"],
            anchor="w",
        ).pack(fill="x", padx=22, pady=(0, 24))

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        nav_items = [
            ("home", "工作台"),
            ("recording", "录音与输出"),
            ("prompts", "提示词管理"),
            ("providers", "AI 供应商"),
            ("dictionary", "替换词典"),
            ("about", "部署与开源"),
        ]
        for key, title in nav_items:
            button = ctk.CTkButton(
                self.sidebar,
                text=title,
                height=42,
                corner_radius=10,
                anchor="w",
                fg_color="transparent",
                hover_color="#dde8f7",
                text_color=self.colors["text"],
                font=ctk.CTkFont(size=14, weight="bold" if key == "home" else "normal"),
                command=lambda k=key: self.show_page(k),
            )
            button.pack(fill="x", padx=14, pady=4)
            self.nav_buttons[key] = button

        self.sidebar_footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_footer.pack(side="bottom", fill="x", padx=16, pady=18)
        self.model_state = ctk.CTkLabel(
            self.sidebar_footer,
            text="模型检查中...",
            text_color=self.colors["muted"],
            anchor="w",
            justify="left",
            font=ctk.CTkFont(size=12),
        )
        self.model_state.pack(fill="x")

        self.main = ctk.CTkFrame(self, fg_color=self.colors["bg"], corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 10))
        header.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(family="Microsoft YaHei UI", size=22, weight="bold"),
            text_color=self.colors["text"],
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="w")
        self.status_label = ctk.CTkLabel(
            header,
            text="准备就绪",
            text_color=self.colors["muted"],
            font=ctk.CTkFont(size=13),
        )
        self.status_label.grid(row=0, column=1, sticky="e")

        self.content = ctk.CTkFrame(self.main, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew", padx=28, pady=(4, 24))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.refresh_model_state()

    def refresh_model_state(self) -> None:
        paths = resolve_model_paths(self.config_data)
        provider = get_active_provider(self.config_data) or {}
        text = f"ASR: {'已就绪' if paths.asr.exists() else '缺失'}\nAI: {provider.get('name', '未配置')}"
        self.model_state.configure(text=text)

    def show_page(self, key: str) -> None:
        {
            "home": self.show_home,
            "recording": self.show_recording,
            "prompts": self.show_prompts,
            "providers": self.show_providers,
            "dictionary": self.show_dictionary,
            "about": self.show_about,
        }[key]()

    def clear_content(self, key: str, title: str) -> None:
        self.current_page = key
        self.title_label.configure(text=title)
        for child in self.content.winfo_children():
            child.destroy()
        for nav_key, button in self.nav_buttons.items():
            active = nav_key == key
            button.configure(
                fg_color=self.colors["primary"] if active else "transparent",
                text_color="#ffffff" if active else self.colors["text"],
                hover_color=self.colors["primary_hover"] if active else "#dde8f7",
            )

    def set_status(self, text: str) -> None:
        self.after(0, lambda: self.status_label.configure(text=text))

    def set_runtime_state(self, text: str) -> None:
        self.float_status = text
        self.set_status(text)
        self.after(0, self.ensure_floating_button)
        self.after(0, self.update_floating_button)

    def preload_models_background(self) -> None:
        def worker() -> None:
            self.set_runtime_state("模型加载中")
            try:
                warmup_models(self.config_data)
                self.set_runtime_state(f"待命 {self.config_data.hotkey}")
            except Exception as exc:
                self.set_runtime_state(f"模型加载失败：{exc}")

        threading.Thread(target=worker, daemon=True).start()

    def track_external_focus(self) -> None:
        hwnd = get_foreground_window()
        if hwnd and not is_own_window(hwnd, self.own_pid):
            self.last_external_hwnd = hwnd
        self.after(300, self.track_external_focus)

    def choose_target_window(self) -> int:
        hwnd = get_foreground_window()
        if hwnd and not is_own_window(hwnd, self.own_pid):
            self.last_external_hwnd = hwnd
            return hwnd
        return self.last_external_hwnd

    def card(self, parent, **kwargs) -> ctk.CTkFrame:
        return ctk.CTkFrame(parent, fg_color=self.colors["panel"], corner_radius=14, border_width=1, border_color=self.colors["line"], **kwargs)

    def show_home(self) -> None:
        self.clear_content("home", "工作台")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(1, weight=1)

        hero = self.card(self.content)
        hero.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        hero.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            hero,
            text="按住热键说话，松开后自动转写和书面化",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.colors["text"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 4))
        ctk.CTkLabel(
            hero,
            text=f"当前热键 {self.config_data.hotkey} · 输出 {self.config_data.output_mode} · 提示词 {(get_active_prompt(self.config_data) or {}).get('name', '未配置')}",
            text_color=self.colors["muted"],
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 18))

        actions = ctk.CTkFrame(hero, fg_color="transparent")
        actions.grid(row=0, column=1, rowspan=2, sticky="e", padx=18)
        self.primary_button(actions, "开始录音", self.start_recording).pack(side="left", padx=5)
        self.secondary_button(actions, "停止转写", self.stop_recording).pack(side="left", padx=5)
        self.secondary_button(actions, "选择音频", self.choose_audio).pack(side="left", padx=5)
        self.secondary_button(actions, "润色剪贴板", self.polish_clipboard).pack(side="left", padx=5)

        grid = ctk.CTkFrame(self.content, fg_color="transparent")
        grid.grid(row=1, column=0, sticky="nsew")
        grid.grid_columnconfigure((0, 1), weight=1)
        grid.grid_rowconfigure((0, 1), weight=1)

        self.raw_text = self.text_card(grid, "原始转写", 0, 0)
        self.normalized_text = self.text_card(grid, "规则整理", 0, 1)
        self.final_text = self.text_card(grid, "最终书面稿", 1, 0, colspan=2)

    def text_card(self, parent, title: str, row: int, column: int, colspan: int = 1) -> ctk.CTkTextbox:
        frame = self.card(parent)
        frame.grid(row=row, column=column, columnspan=colspan, sticky="nsew", padx=6, pady=6)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=14, weight="bold"), anchor="w").grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        text = ctk.CTkTextbox(frame, corner_radius=10, border_width=0, fg_color="#f8fafd", text_color=self.colors["text"], wrap="word")
        text.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        return text

    def primary_button(self, parent, text: str, command) -> ctk.CTkButton:
        return ctk.CTkButton(parent, text=text, command=command, height=36, corner_radius=9, fg_color=self.colors["primary"], hover_color=self.colors["primary_hover"])

    def secondary_button(self, parent, text: str, command) -> ctk.CTkButton:
        return ctk.CTkButton(parent, text=text, command=command, height=36, corner_radius=9, fg_color="#eef4ff", hover_color="#dfeaff", text_color=self.colors["primary"])

    def show_recording(self) -> None:
        self.clear_content("recording", "录音与输出")
        wrap = ctk.CTkScrollableFrame(self.content, fg_color="transparent")
        wrap.grid(row=0, column=0, sticky="nsew")
        wrap.grid_columnconfigure(0, weight=1)

        self.hotkey_var = ctk.StringVar(value=self.config_data.hotkey)
        self.model_root_var = ctk.StringVar(value=self.config_data.model_root)
        self.output_mode_var = ctk.StringVar(value=self.config_data.output_mode)
        switches = {
            "hold": ("按住说话，松开结束", self.config_data.hold_to_record),
            "float": ("显示录音悬浮提示", self.config_data.show_floating_indicator),
            "autostart": ("开机自启动", autostart.is_enabled()),
            "minimized": ("启动后最小化", self.config_data.start_minimized),
            "copy": ("复制结果到剪贴板", self.config_data.copy_result_to_clipboard),
            "paste": ("处理完成后自动粘贴", self.config_data.auto_paste),
            "ai": ("启用 DeepSeek 书面化", self.config_data.enable_ai_polish),
            "history": ("保存历史记录", self.config_data.save_history),
            "numbers": ("智能数字转换", self.config_data.smart_numbers),
            "filler": ("过滤口语词", self.config_data.filter_filler_words),
            "strip": ("删除结尾标点", self.config_data.strip_trailing_punctuation),
            "keep_raw": ("剪贴板保留原始转写", self.config_data.keep_raw_clipboard),
        }
        self.switch_vars = {key: ctk.BooleanVar(value=value) for key, (_, value) in switches.items()}

        panel = self.card(wrap)
        panel.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        panel.grid_columnconfigure(1, weight=1)
        self.form_entry(panel, 0, "录音热键", self.hotkey_var)
        self.form_entry(panel, 1, "模型目录", self.model_root_var, browse=True)
        self.form_option(panel, 2, "默认输出", self.output_mode_var, ["polished", "normalized", "raw"])

        toggles = self.card(wrap)
        toggles.grid(row=1, column=0, sticky="ew")
        toggles.grid_columnconfigure((0, 1), weight=1)
        for idx, (key, (label, _)) in enumerate(switches.items()):
            ctk.CTkSwitch(toggles, text=label, variable=self.switch_vars[key], progress_color=self.colors["primary"]).grid(
                row=idx // 2, column=idx % 2, sticky="w", padx=18, pady=12
            )

        actions = ctk.CTkFrame(wrap, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=18)
        self.secondary_button(actions, "复制本机模型到项目", self.init_models).pack(side="left")
        self.primary_button(actions, "保存设置", self.save_recording_settings).pack(side="right")

    def form_entry(self, parent, row: int, label: str, var, browse: bool = False) -> None:
        ctk.CTkLabel(parent, text=label, anchor="w", text_color=self.colors["muted"]).grid(row=row, column=0, sticky="w", padx=18, pady=12)
        ctk.CTkEntry(parent, textvariable=var, height=36, corner_radius=9).grid(row=row, column=1, sticky="ew", padx=10, pady=12)
        if browse:
            self.secondary_button(parent, "选择", lambda: self.browse_dir(var)).grid(row=row, column=2, padx=18, pady=12)

    def form_option(self, parent, row: int, label: str, var, values: list[str]) -> None:
        ctk.CTkLabel(parent, text=label, anchor="w", text_color=self.colors["muted"]).grid(row=row, column=0, sticky="w", padx=18, pady=12)
        ctk.CTkOptionMenu(parent, variable=var, values=values, height=36, corner_radius=9).grid(row=row, column=1, sticky="w", padx=10, pady=12)

    def show_providers(self) -> None:
        self.clear_content("providers", "AI 供应商")
        self.two_column_editor("provider")

    def show_prompts(self) -> None:
        self.clear_content("prompts", "提示词管理")
        self.two_column_editor("prompt")

    def show_dictionary(self) -> None:
        self.clear_content("dictionary", "替换词典")
        self.two_column_editor("rule")

    def two_column_editor(self, kind: str) -> None:
        self.content.grid_columnconfigure(0, weight=0)
        self.content.grid_columnconfigure(1, weight=1)
        left = self.card(self.content, width=280)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 14))
        left.grid_propagate(False)
        list_frame = ctk.CTkScrollableFrame(left, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)

        items = self.config_data.providers if kind == "provider" else self.config_data.prompts if kind == "prompt" else self.config_data.replacement_rules
        for idx, item in enumerate(items):
            title = item.get("name") if kind != "rule" else f"{item.get('from', '')} -> {item.get('to', '')}"
            if kind == "provider" and item.get("id") == self.config_data.ai_provider:
                title += "  默认"
            if kind == "prompt" and item.get("id") == self.config_data.active_prompt_id:
                title += "  默认"
            ctk.CTkButton(
                list_frame,
                text=title or "未命名",
                height=38,
                corner_radius=9,
                fg_color="#eef4ff",
                hover_color="#dfeaff",
                text_color=self.colors["text"],
                anchor="w",
                command=lambda i=idx, k=kind: self.load_editor(k, i),
            ).pack(fill="x", pady=4)

        bottom = ctk.CTkFrame(left, fg_color="transparent")
        bottom.pack(fill="x", padx=12, pady=(0, 12))
        self.secondary_button(bottom, "添加", lambda: self.add_item(kind)).pack(side="left", expand=True, fill="x", padx=(0, 5))
        self.secondary_button(bottom, "删除", lambda: self.delete_item(kind)).pack(side="left", expand=True, fill="x", padx=(5, 0))

        self.editor = self.card(self.content)
        self.editor.grid(row=0, column=1, sticky="nsew")
        self.editor.grid_columnconfigure(1, weight=1)
        self.editor.grid_rowconfigure(4, weight=1)
        self.load_editor(kind, 0 if items else None)

    def load_editor(self, kind: str, index: int | None) -> None:
        for child in self.editor.winfo_children():
            child.destroy()
        if index is None:
            return
        if kind == "provider":
            self.provider_index = index
            item = self.config_data.providers[index]
            self.provider_name = ctk.StringVar(value=item.get("name", ""))
            self.provider_base = ctk.StringVar(value=item.get("base_url", ""))
            self.provider_model = ctk.StringVar(value=item.get("model", ""))
            self.provider_key = ctk.StringVar(value=item.get("api_key", ""))
            self.form_entry(self.editor, 0, "名称", self.provider_name)
            self.form_entry(self.editor, 1, "Base URL", self.provider_base)
            self.form_entry(self.editor, 2, "模型名", self.provider_model)
            self.form_entry(self.editor, 3, "API Key", self.provider_key)
            self.primary_button(self.editor, "设为默认并保存", self.save_provider).grid(row=5, column=1, sticky="e", padx=18, pady=18)
        elif kind == "prompt":
            self.prompt_index = index
            item = self.config_data.prompts[index]
            self.prompt_name = ctk.StringVar(value=item.get("name", ""))
            self.prompt_tag = ctk.StringVar(value=item.get("tag", "自定义"))
            self.form_entry(self.editor, 0, "名称", self.prompt_name)
            self.form_entry(self.editor, 1, "标签", self.prompt_tag)
            ctk.CTkLabel(self.editor, text="内容", text_color=self.colors["muted"]).grid(row=2, column=0, sticky="nw", padx=18, pady=12)
            self.prompt_text = ctk.CTkTextbox(self.editor, corner_radius=10, fg_color="#f8fafd")
            self.prompt_text.grid(row=2, column=1, sticky="nsew", padx=10, pady=12)
            self.prompt_text.insert("1.0", item.get("prompt", ""))
            self.primary_button(self.editor, "设为默认并保存", self.save_prompt).grid(row=5, column=1, sticky="e", padx=18, pady=18)
        else:
            self.rule_index = index
            item = self.config_data.replacement_rules[index]
            self.rule_from = ctk.StringVar(value=item.get("from", ""))
            self.rule_to = ctk.StringVar(value=item.get("to", ""))
            self.rule_enabled = ctk.BooleanVar(value=bool(item.get("enabled", True)))
            self.form_entry(self.editor, 0, "错误词", self.rule_from)
            self.form_entry(self.editor, 1, "正确词", self.rule_to)
            ctk.CTkSwitch(self.editor, text="启用这条规则", variable=self.rule_enabled, progress_color=self.colors["primary"]).grid(row=2, column=1, sticky="w", padx=10, pady=12)
            self.primary_button(self.editor, "保存词典", self.save_rule).grid(row=5, column=1, sticky="e", padx=18, pady=18)

    def show_about(self) -> None:
        self.clear_content("about", "部署与开源")
        panel = self.card(self.content)
        panel.grid(row=0, column=0, sticky="nsew")
        text = ctk.CTkTextbox(panel, corner_radius=12, fg_color="#f8fafd", wrap="word")
        text.pack(fill="both", expand=True, padx=18, pady=18)
        text.insert(
            "1.0",
            "普通用户入口：双击 语言转写.vbs，无命令行窗口。\n\n"
            "开发排错入口：语言转写.bat doctor / transcribe / run。\n\n"
            "复制到其他电脑：源码 + install.ps1 + 官方模型目录 + 用户自己的 API Key。\n\n"
            "打包 exe：运行 package.ps1，产物是 dist\\YuyanZhuanxie\\YuyanZhuanxie.exe，已配置为无控制台窗口。\n\n"
            "开源时不要提交 .venv、.local_models、config.json、history.jsonl、API Key、VocoType 程序文件。",
        )
        text.configure(state="disabled")

    def browse_dir(self, var) -> None:
        selected = filedialog.askdirectory()
        if selected:
            var.set(selected)

    def save_recording_settings(self) -> None:
        self.config_data.hotkey = self.hotkey_var.get().strip() or "F2"
        self.config_data.model_root = self.model_root_var.get().strip() or ".local_models/iic"
        self.config_data.output_mode = self.output_mode_var.get()
        self.config_data.hold_to_record = self.switch_vars["hold"].get()
        self.config_data.show_floating_indicator = self.switch_vars["float"].get()
        self.config_data.start_minimized = self.switch_vars["minimized"].get()
        self.config_data.copy_result_to_clipboard = self.switch_vars["copy"].get()
        self.config_data.auto_paste = self.switch_vars["paste"].get()
        self.config_data.enable_ai_polish = self.switch_vars["ai"].get()
        self.config_data.save_history = self.switch_vars["history"].get()
        self.config_data.smart_numbers = self.switch_vars["numbers"].get()
        self.config_data.filter_filler_words = self.switch_vars["filler"].get()
        self.config_data.strip_trailing_punctuation = self.switch_vars["strip"].get()
        self.config_data.keep_raw_clipboard = self.switch_vars["keep_raw"].get()
        autostart.set_enabled(self.switch_vars["autostart"].get())
        save_config(self.config_data)
        self.register_hotkey()
        self.refresh_model_state()
        self.set_runtime_state(f"待命 {self.config_data.hotkey}")
        if self.hotkey_error:
            self.set_runtime_state(f"热键失败：{self.hotkey_error}")
        messagebox.showinfo("语言转写", "设置已保存。")

    def add_item(self, kind: str) -> None:
        if kind == "provider":
            self.config_data.providers.append({"id": uuid.uuid4().hex, "name": "新供应商", "base_url": "", "model": "", "api_key": ""})
            self.show_providers()
        elif kind == "prompt":
            self.config_data.prompts.append({"id": uuid.uuid4().hex, "name": "新提示词", "tag": "自定义", "prompt": ""})
            self.show_prompts()
        else:
            self.config_data.replacement_rules.append({"from": "", "to": "", "enabled": True})
            self.show_dictionary()

    def delete_item(self, kind: str) -> None:
        if kind == "provider":
            if len(self.config_data.providers) <= 1:
                return
            removed = self.config_data.providers.pop(self.provider_index)
            if self.config_data.ai_provider == removed.get("id"):
                self.config_data.ai_provider = self.config_data.providers[0]["id"]
            save_config(self.config_data)
            self.show_providers()
        elif kind == "prompt":
            if len(self.config_data.prompts) <= 1:
                return
            removed = self.config_data.prompts.pop(self.prompt_index)
            if self.config_data.active_prompt_id == removed.get("id"):
                self.config_data.active_prompt_id = self.config_data.prompts[0]["id"]
            save_config(self.config_data)
            self.show_prompts()
        else:
            if self.config_data.replacement_rules:
                self.config_data.replacement_rules.pop(self.rule_index)
            save_config(self.config_data)
            self.show_dictionary()

    def save_provider(self) -> None:
        item = self.config_data.providers[self.provider_index]
        item.update(
            {
                "name": self.provider_name.get().strip() or "未命名",
                "base_url": self.provider_base.get().strip(),
                "model": self.provider_model.get().strip(),
                "api_key": self.provider_key.get().strip(),
            }
        )
        self.config_data.ai_provider = item["id"]
        save_config(self.config_data)
        self.refresh_model_state()
        self.set_status("AI 供应商已保存")
        self.show_providers()

    def save_prompt(self) -> None:
        item = self.config_data.prompts[self.prompt_index]
        item.update({"name": self.prompt_name.get().strip() or "未命名", "tag": self.prompt_tag.get().strip() or "自定义", "prompt": self.prompt_text.get("1.0", "end").strip()})
        self.config_data.active_prompt_id = item["id"]
        save_config(self.config_data)
        self.set_status("提示词已保存")
        self.show_prompts()

    def save_rule(self) -> None:
        item = self.config_data.replacement_rules[self.rule_index]
        item.update({"from": self.rule_from.get(), "to": self.rule_to.get(), "enabled": self.rule_enabled.get()})
        save_config(self.config_data)
        self.set_status("替换词典已保存")
        self.show_dictionary()

    def init_models(self) -> None:
        def worker() -> None:
            try:
                dest = copy_cached_models()
                self.set_status(f"模型已准备：{dest}")
            except Exception as exc:
                self.set_status(f"模型复制失败：{exc}")

        threading.Thread(target=worker, daemon=True).start()

    def register_hotkey(self) -> None:
        self.hotkey_error = ""
        try:
            import keyboard
        except ImportError:
            self.hotkey_error = "缺少 keyboard 依赖"
            return
        try:
            keyboard.unhook_all()
            key = (self.config_data.hotkey or "F2").lower()
            if self.config_data.hold_to_record:
                keyboard.on_press_key(key, lambda event: self.after(0, self.start_recording), suppress=False)
                keyboard.on_release_key(key, lambda event: self.after(0, self.stop_recording), suppress=False)
            else:
                keyboard.add_hotkey(key, lambda: self.after(0, self.toggle_recording))
        except Exception as exc:
            self.hotkey_error = str(exc)

    def toggle_recording(self) -> None:
        self.stop_recording() if self.recording else self.start_recording()

    def start_recording(self) -> None:
        if self.recording:
            return
        try:
            self.target_hwnd = self.choose_target_window()
            self.recorder.start()
            self.recording = True
            self.started_at = time.time()
            self.set_runtime_state("录音中 00:00")
        except Exception as exc:
            messagebox.showerror("录音失败", str(exc))

    def stop_recording(self) -> None:
        if not self.recording:
            return
        try:
            wav = self.recorder.stop()
            self.recording = False
            self.set_runtime_state("转写中")
            self.process_audio(wav)
        except Exception as exc:
            self.recording = False
            self.set_runtime_state(f"录音失败：{exc}")
            messagebox.showerror("停止录音失败", str(exc))

    def choose_audio(self) -> None:
        audio = filedialog.askopenfilename(title="选择音频文件", filetypes=[("Audio", "*.wav *.mp3 *.m4a *.aac *.flac"), ("All files", "*.*")])
        if audio:
            self.process_audio(Path(audio))

    def polish_clipboard(self) -> None:
        try:
            self.process_text(read_clipboard(), "clipboard")
        except Exception as exc:
            messagebox.showerror("读取剪贴板失败", str(exc))

    def process_audio(self, audio_path: Path) -> None:
        def worker() -> None:
            try:
                self.set_runtime_state("本地转写中")
                raw = transcribe_audio(audio_path, self.config_data)
                self.process_text(raw, str(audio_path), same_thread=True)
            except Exception as exc:
                self.set_runtime_state(f"转写失败：{exc}")

        threading.Thread(target=worker, daemon=True).start()

    def process_text(self, raw: str, source: str, same_thread: bool = False) -> None:
        def worker() -> None:
            normalized = normalize_text(raw, self.config_data)
            polished = normalized
            if self.config_data.enable_ai_polish:
                try:
                    self.set_runtime_state("DeepSeek 优化中")
                    polished = polish_text(normalized, self.config_data)
                except Exception as exc:
                    polished = normalized
                    self.set_runtime_state(f"AI 跳过：{exc}")
            else:
                polished = normalized
                self.set_runtime_state("已跳过 DeepSeek")
            output = choose_output(raw, normalized, polished, self.config_data)
            if self.config_data.copy_result_to_clipboard:
                clip = raw if self.config_data.keep_raw_clipboard else output
                self.after(0, lambda: write_clipboard(clip))
            if self.config_data.save_history:
                append_history(raw, output, source)
            if self.config_data.auto_paste:
                self.after(250, self.send_paste)
            self.after(0, lambda: self.fill_outputs(raw, normalized, output))
            self.set_runtime_state("已完成")

        worker() if same_thread else threading.Thread(target=worker, daemon=True).start()

    def fill_outputs(self, raw: str, normalized: str, final: str) -> None:
        if self.current_page != "home":
            self.show_home()
        for widget, value in [(self.raw_text, raw), (self.normalized_text, normalized), (self.final_text, final)]:
            widget.delete("1.0", "end")
            widget.insert("1.0", value)

    def send_paste(self) -> None:
        if paste_to_window(self.target_hwnd):
            self.set_runtime_state("已粘贴")
        else:
            self.set_runtime_state("自动粘贴失败")

    def show_indicator(self) -> None:
        self.ensure_floating_button()

    def ensure_floating_button(self) -> None:
        if not self.config_data.show_floating_indicator:
            return
        if self.float_window is None or not self.float_window.winfo_exists():
            self.float_window = None
            self.float_label = None
            self.create_floating_button()
        else:
            self.float_window.deiconify()
            self.float_window.lift()
            self.float_window.attributes("-topmost", True)

    def create_floating_button(self) -> None:
        if not self.config_data.show_floating_indicator or self.float_window is not None:
            return
        win = tk.Toplevel()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-toolwindow", True)
        win.configure(bg="#05070c")
        win.wm_attributes("-alpha", 0.96)
        self.float_label = tk.Label(
            win,
            text="● 语言转写",
            bg="#05070c",
            fg="#ffffff",
            padx=18,
            pady=10,
            font=("Microsoft YaHei UI", 11, "bold"),
        )
        self.float_label.pack()
        self.float_label.bind("<Button-1>", lambda _event: self.toggle_recording())
        win.bind("<Button-1>", lambda _event: self.toggle_recording())
        win.geometry(f"+{self.winfo_screenwidth() - 210}+72")
        win.lift()
        self.float_window = win
        self.update_floating_button()

    def update_floating_button(self) -> None:
        if self.float_window is None or self.float_label is None:
            return
        if self.recording:
            elapsed = int(time.time() - self.started_at)
            text = f"●  {elapsed // 60:02d}:{elapsed % 60:02d}"
            fg = "#ff4d5a"
        else:
            text = self.float_status
            fg = "#ffffff"
            if "待命" in text:
                text = f"● {text}"
                fg = "#38d27a"
            elif "加载" in text or "转写" in text or "DeepSeek" in text:
                text = f"● {text}"
                fg = "#ffcc66"
            elif "失败" in text or "跳过" in text:
                text = f"● {text}"
                fg = "#ff6b6b"
            else:
                text = f"● {text}"
        self.float_label.configure(text=text, fg=fg)
        self.float_window.after(250 if self.recording else 1000, self.update_floating_button)

    def hide_indicator(self) -> None:
        self.set_runtime_state(f"待命 {self.config_data.hotkey}")

    def on_close(self) -> None:
        try:
            import keyboard

            keyboard.unhook_all()
        except Exception:
            pass
        self.destroy()


def run_modern_gui() -> None:
    app = ModernTranscriberApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
