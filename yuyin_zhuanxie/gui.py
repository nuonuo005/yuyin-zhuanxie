from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import autostart
from .asr import copy_cached_models, resolve_model_paths, transcribe_audio
from .clipboard import read_clipboard, write_clipboard
from .config import AppConfig, get_active_prompt, get_active_provider, load_config, save_config
from .deepseek import polish_text
from .history import append_history
from .recorder import AudioRecorder
from .text_tools import choose_output, normalize_text


class TranscriberApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("语言转写")
        self.geometry("1120x720")
        self.minsize(980, 640)
        self.config = load_config()
        self.recorder = AudioRecorder()
        self.recording = False
        self.record_started_at = 0.0
        self.hotkey_error = ""
        self.current_page = "home"
        self.provider_index = 0
        self.prompt_index = 0
        self.rule_index = 0
        self.float_window: tk.Toplevel | None = None

        self._setup_style()
        self._build_shell()
        self.show_home()
        self.register_hotkey()
        if self.config.start_minimized:
            self.iconify()

    def _setup_style(self) -> None:
        self.configure(bg="#f6f8fb")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Microsoft YaHei UI", 10))
        style.configure("TButton", padding=(12, 7), borderwidth=0)
        style.configure("Primary.TButton", background="#2f73ff", foreground="white")
        style.map("Primary.TButton", background=[("active", "#1f5ee8")])
        style.configure("Nav.TButton", anchor="w", padding=(16, 10), background="#f6f8fb")
        style.configure("NavActive.TButton", anchor="w", padding=(16, 10), background="#e8f0ff", foreground="#0649b8")
        style.configure("TCheckbutton", background="#ffffff")
        style.configure("TLabelframe", background="#ffffff")
        style.configure("TLabelframe.Label", background="#ffffff", font=("Microsoft YaHei UI", 10, "bold"))

    def _build_shell(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self.nav = tk.Frame(self, bg="#f6f8fb", width=210)
        self.nav.grid(row=0, column=0, sticky="ns")
        self.nav.grid_propagate(False)

        tk.Label(
            self.nav,
            text="语言转写",
            bg="#f6f8fb",
            fg="#0b1f40",
            font=("Microsoft YaHei UI", 18, "bold"),
            anchor="w",
        ).pack(fill="x", padx=18, pady=(22, 4))
        tk.Label(
            self.nav,
            text="本地语音识别 + AI 书面化",
            bg="#f6f8fb",
            fg="#637083",
            anchor="w",
        ).pack(fill="x", padx=18, pady=(0, 18))

        self.nav_buttons: dict[str, ttk.Button] = {}
        items = [
            ("home", "主页"),
            ("recording", "录音与输出"),
            ("prompts", "提示词管理"),
            ("providers", "AI 供应商"),
            ("dictionary", "替换词典"),
            ("about", "部署说明"),
        ]
        for key, text in items:
            button = ttk.Button(self.nav, text=text, style="Nav.TButton", command=lambda k=key: self.show_page(k))
            button.pack(fill="x", padx=8, pady=2)
            self.nav_buttons[key] = button

        self.main = tk.Frame(self, bg="#ffffff")
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.columnconfigure(0, weight=1)
        self.main.rowconfigure(1, weight=1)

        self.header = tk.Frame(self.main, bg="#ffffff")
        self.header.grid(row=0, column=0, sticky="ew", padx=24, pady=(18, 6))
        self.header.columnconfigure(0, weight=1)
        self.title_label = tk.Label(self.header, text="", bg="#ffffff", fg="#0b1f40", font=("Microsoft YaHei UI", 16, "bold"))
        self.title_label.grid(row=0, column=0, sticky="w")
        self.status_var = tk.StringVar(value="准备就绪")
        tk.Label(self.header, textvariable=self.status_var, bg="#ffffff", fg="#637083").grid(row=0, column=1, sticky="e")

        self.body = tk.Frame(self.main, bg="#ffffff")
        self.body.grid(row=1, column=0, sticky="nsew", padx=24, pady=12)
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)

    def show_page(self, key: str) -> None:
        pages = {
            "home": self.show_home,
            "recording": self.show_recording,
            "prompts": self.show_prompts,
            "providers": self.show_providers,
            "dictionary": self.show_dictionary,
            "about": self.show_about,
        }
        pages[key]()

    def _clear_body(self, page: str, title: str) -> None:
        self.current_page = page
        self.title_label.config(text=title)
        for child in self.body.winfo_children():
            child.destroy()
        for key, button in self.nav_buttons.items():
            button.configure(style="NavActive.TButton" if key == page else "Nav.TButton")

    def set_status(self, text: str) -> None:
        self.after(0, lambda: self.status_var.set(text))

    def show_home(self) -> None:
        self._clear_body("home", "主页")
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(1, weight=1)

        toolbar = tk.Frame(self.body, bg="#ffffff")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Button(toolbar, text="开始录音", style="Primary.TButton", command=self.start_recording).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="停止并转写", command=self.stop_recording).pack(side="left", padx=8)
        ttk.Button(toolbar, text="选择音频文件", command=self.choose_audio).pack(side="left", padx=8)
        ttk.Button(toolbar, text="润色剪贴板", command=self.polish_clipboard).pack(side="left", padx=8)
        ttk.Button(toolbar, text="复制最终稿", command=self.copy_final_text).pack(side="right")

        paned = ttk.PanedWindow(self.body, orient="vertical")
        paned.grid(row=1, column=0, sticky="nsew")
        self.raw_text = self._text_panel(paned, "原始转写")
        self.normalized_text = self._text_panel(paned, "规则整理")
        self.final_text = self._text_panel(paned, "最终书面稿")

        hotkey = self.config.hotkey or "F2"
        help_text = f"热键：{hotkey}。当前输出模式：{self.config.output_mode}。"
        if self.hotkey_error:
            help_text += f" 热键未启用：{self.hotkey_error}"
        tk.Label(self.body, text=help_text, bg="#ffffff", fg="#7b8798", anchor="w").grid(row=2, column=0, sticky="ew", pady=(10, 0))

    def _text_panel(self, parent: ttk.PanedWindow, title: str) -> tk.Text:
        frame = ttk.LabelFrame(parent, text=title)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        text = tk.Text(frame, height=7, wrap="word", relief="flat", bg="#f8fafc", fg="#13233a", padx=12, pady=10)
        text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        parent.add(frame, weight=1)
        return text

    def show_recording(self) -> None:
        self._clear_body("recording", "录音与输出")
        frame = ttk.LabelFrame(self.body, text="输入与录音")
        frame.pack(fill="x", pady=(0, 14))
        self.hotkey_var = tk.StringVar(value=self.config.hotkey)
        self.model_root_var = tk.StringVar(value=self.config.model_root)
        self.hold_var = tk.BooleanVar(value=self.config.hold_to_record)
        self.float_var = tk.BooleanVar(value=self.config.show_floating_indicator)
        self.autostart_var = tk.BooleanVar(value=autostart.is_enabled())
        self.start_minimized_var = tk.BooleanVar(value=self.config.start_minimized)
        self._row_entry(frame, 0, "录音热键", self.hotkey_var)
        self._row_entry(frame, 1, "模型目录", self.model_root_var, browse=True)
        self._check(frame, 2, "按住说话，松开结束", self.hold_var)
        self._check(frame, 3, "显示录音状态提示", self.float_var)
        self._check(frame, 4, "开机自启动", self.autostart_var)
        self._check(frame, 5, "启动后最小化", self.start_minimized_var)

        out = ttk.LabelFrame(self.body, text="文本输出")
        out.pack(fill="x", pady=(0, 14))
        self.copy_var = tk.BooleanVar(value=self.config.copy_result_to_clipboard)
        self.paste_var = tk.BooleanVar(value=self.config.auto_paste)
        self.history_var = tk.BooleanVar(value=self.config.save_history)
        self.filler_var = tk.BooleanVar(value=self.config.filter_filler_words)
        self.strip_var = tk.BooleanVar(value=self.config.strip_trailing_punctuation)
        self.keep_raw_var = tk.BooleanVar(value=self.config.keep_raw_clipboard)
        self.smart_numbers_var = tk.BooleanVar(value=self.config.smart_numbers)
        self.output_mode_var = tk.StringVar(value=self.config.output_mode)
        self._combo(out, 0, "默认输出", self.output_mode_var, ["polished", "normalized", "raw"])
        self._check(out, 1, "复制最终结果到剪贴板", self.copy_var)
        self._check(out, 2, "处理完成后自动粘贴到当前输入框", self.paste_var)
        self._check(out, 3, "保存历史记录", self.history_var)
        self._check(out, 4, "智能数字转换", self.smart_numbers_var)
        self._check(out, 5, "过滤口语词", self.filler_var)
        self._check(out, 6, "删除结尾标点", self.strip_var)
        self._check(out, 7, "保留识别文本到剪贴板", self.keep_raw_var)

        actions = tk.Frame(self.body, bg="#ffffff")
        actions.pack(fill="x")
        ttk.Button(actions, text="复制本机模型到项目", command=self.init_models).pack(side="left")
        ttk.Button(actions, text="保存设置", style="Primary.TButton", command=self.save_recording_settings).pack(side="right")

    def _row_entry(self, parent, row: int, label: str, var: tk.StringVar, browse: bool = False) -> None:
        parent.columnconfigure(1, weight=1)
        tk.Label(parent, text=label, bg="#ffffff", fg="#24364f", anchor="w").grid(row=row, column=0, sticky="w", padx=14, pady=10)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=10, pady=10)
        if browse:
            ttk.Button(parent, text="选择", command=lambda: self.browse_dir(var)).grid(row=row, column=2, padx=12, pady=10)

    def _check(self, parent, row: int, text: str, var: tk.BooleanVar) -> None:
        ttk.Checkbutton(parent, text=text, variable=var).grid(row=row, column=1, sticky="w", padx=10, pady=8)

    def _combo(self, parent, row: int, label: str, var: tk.StringVar, values: list[str]) -> None:
        parent.columnconfigure(1, weight=1)
        tk.Label(parent, text=label, bg="#ffffff", fg="#24364f", anchor="w").grid(row=row, column=0, sticky="w", padx=14, pady=10)
        ttk.Combobox(parent, textvariable=var, values=values, state="readonly").grid(row=row, column=1, sticky="w", padx=10, pady=10)

    def show_providers(self) -> None:
        self._clear_body("providers", "AI 供应商")
        self.body.columnconfigure(1, weight=1)
        self.body.rowconfigure(0, weight=1)

        left = tk.Frame(self.body, bg="#ffffff")
        left.grid(row=0, column=0, sticky="ns", padx=(0, 18))
        self.provider_list = tk.Listbox(left, width=26, height=18, activestyle="dotbox")
        self.provider_list.pack(fill="both", expand=True)
        for provider in self.config.providers:
            marker = " *" if provider.get("id") == self.config.ai_provider else ""
            self.provider_list.insert("end", f"{provider.get('name', '未命名')}{marker}")
        self.provider_list.bind("<<ListboxSelect>>", self.load_provider_form)
        ttk.Button(left, text="添加", command=self.add_provider).pack(fill="x", pady=(10, 4))
        ttk.Button(left, text="删除", command=self.delete_provider).pack(fill="x")

        form = ttk.LabelFrame(self.body, text="供应商配置")
        form.grid(row=0, column=1, sticky="nsew")
        self.provider_name_var = tk.StringVar()
        self.provider_base_var = tk.StringVar()
        self.provider_model_var = tk.StringVar()
        self.provider_key_var = tk.StringVar()
        self._row_entry(form, 0, "名称", self.provider_name_var)
        self._row_entry(form, 1, "Base URL", self.provider_base_var)
        self._row_entry(form, 2, "模型名", self.provider_model_var)
        self._row_entry(form, 3, "API Key", self.provider_key_var)
        ttk.Button(form, text="设为默认并保存", style="Primary.TButton", command=self.save_provider).grid(row=4, column=1, sticky="e", padx=10, pady=16)
        if self.config.providers:
            self.provider_list.selection_set(0)
            self.load_provider_form()

    def show_prompts(self) -> None:
        self._clear_body("prompts", "提示词管理")
        self.body.columnconfigure(1, weight=1)
        self.body.rowconfigure(0, weight=1)

        left = tk.Frame(self.body, bg="#ffffff")
        left.grid(row=0, column=0, sticky="ns", padx=(0, 18))
        self.prompt_list = tk.Listbox(left, width=26, height=18)
        self.prompt_list.pack(fill="both", expand=True)
        for prompt in self.config.prompts:
            marker = " *" if prompt.get("id") == self.config.active_prompt_id else ""
            self.prompt_list.insert("end", f"{prompt.get('name', '未命名')}{marker}")
        self.prompt_list.bind("<<ListboxSelect>>", self.load_prompt_form)
        ttk.Button(left, text="添加", command=self.add_prompt).pack(fill="x", pady=(10, 4))
        ttk.Button(left, text="删除", command=self.delete_prompt).pack(fill="x")

        form = ttk.LabelFrame(self.body, text="提示词")
        form.grid(row=0, column=1, sticky="nsew")
        form.rowconfigure(2, weight=1)
        form.columnconfigure(1, weight=1)
        self.prompt_name_var = tk.StringVar()
        self.prompt_tag_var = tk.StringVar()
        self._row_entry(form, 0, "名称", self.prompt_name_var)
        self._row_entry(form, 1, "标签", self.prompt_tag_var)
        tk.Label(form, text="内容", bg="#ffffff", fg="#24364f", anchor="nw").grid(row=2, column=0, sticky="nw", padx=14, pady=10)
        self.prompt_text = tk.Text(form, height=16, wrap="word", relief="solid", bd=1, padx=10, pady=10)
        self.prompt_text.grid(row=2, column=1, sticky="nsew", padx=10, pady=10)
        ttk.Button(form, text="设为默认并保存", style="Primary.TButton", command=self.save_prompt).grid(row=3, column=1, sticky="e", padx=10, pady=16)
        if self.config.prompts:
            self.prompt_list.selection_set(0)
            self.load_prompt_form()

    def show_dictionary(self) -> None:
        self._clear_body("dictionary", "替换词典")
        self.body.columnconfigure(1, weight=1)
        left = tk.Frame(self.body, bg="#ffffff")
        left.grid(row=0, column=0, sticky="ns", padx=(0, 18))
        self.rule_list = tk.Listbox(left, width=30, height=20)
        self.rule_list.pack(fill="both", expand=True)
        for rule in self.config.replacement_rules:
            self.rule_list.insert("end", f"{rule.get('from', '')} -> {rule.get('to', '')}")
        self.rule_list.bind("<<ListboxSelect>>", self.load_rule_form)
        ttk.Button(left, text="添加", command=self.add_rule).pack(fill="x", pady=(10, 4))
        ttk.Button(left, text="删除", command=self.delete_rule).pack(fill="x")

        form = ttk.LabelFrame(self.body, text="替换规则")
        form.grid(row=0, column=1, sticky="new")
        self.rule_from_var = tk.StringVar()
        self.rule_to_var = tk.StringVar()
        self.rule_enabled_var = tk.BooleanVar(value=True)
        self._row_entry(form, 0, "错误词（识别结果）", self.rule_from_var)
        self._row_entry(form, 1, "正确词（替换为）", self.rule_to_var)
        self._check(form, 2, "启用这条规则", self.rule_enabled_var)
        ttk.Button(form, text="保存词典", style="Primary.TButton", command=self.save_rule).grid(row=3, column=1, sticky="e", padx=10, pady=16)
        if self.config.replacement_rules:
            self.rule_list.selection_set(0)
            self.load_rule_form()

    def show_about(self) -> None:
        self._clear_body("about", "部署说明")
        text = tk.Text(self.body, wrap="word", relief="flat", bg="#f8fafc", padx=18, pady=18)
        text.pack(fill="both", expand=True)
        text.insert(
            "1.0",
            (
                "当前版本已经是可视化客户端原型：\n\n"
                "1. 本地模型目录默认使用项目内 .local_models/iic，也可以在“录音与输出”里改成别的目录。\n"
                "2. AI 供应商走 OpenAI-compatible API，默认 DeepSeek，也可以配置 Ollama、LM Studio、OpenAI、Qwen 等。\n"
                "3. 提示词、热键、输出模式、替换词典都会保存到 config.json。\n"
                "4. 开机自启动通过 Windows 启动文件夹创建 bat，不写注册表。\n"
                "5. 开源发布时不要提交 .venv、.local_models、config.json、history.jsonl 和任何 API Key。\n\n"
                "复制到另一台电脑的最小流程：\n"
                "复制项目源码 -> 运行 install.ps1 -> 放入/下载 FunASR ONNX 模型 -> 填写 AI Key -> 双击 语言转写.bat。\n\n"
                "如果要做成真正安装包，下一步建议用 PyInstaller 打包 GUI，或把当前 Python 后端迁到 Tauri 前端。"
            ),
        )
        text.configure(state="disabled")

    def browse_dir(self, var: tk.StringVar) -> None:
        selected = filedialog.askdirectory()
        if selected:
            var.set(selected)

    def save_recording_settings(self) -> None:
        self.config.hotkey = self.hotkey_var.get().strip() or "F2"
        self.config.model_root = self.model_root_var.get().strip() or ".local_models/iic"
        self.config.hold_to_record = self.hold_var.get()
        self.config.show_floating_indicator = self.float_var.get()
        self.config.start_minimized = self.start_minimized_var.get()
        self.config.copy_result_to_clipboard = self.copy_var.get()
        self.config.auto_paste = self.paste_var.get()
        self.config.save_history = self.history_var.get()
        self.config.smart_numbers = self.smart_numbers_var.get()
        self.config.filter_filler_words = self.filler_var.get()
        self.config.strip_trailing_punctuation = self.strip_var.get()
        self.config.keep_raw_clipboard = self.keep_raw_var.get()
        self.config.output_mode = self.output_mode_var.get()
        autostart.set_enabled(self.autostart_var.get())
        save_config(self.config)
        self.register_hotkey()
        self.set_status("设置已保存")
        messagebox.showinfo("语言转写", "设置已保存。")

    def init_models(self) -> None:
        def worker() -> None:
            try:
                dest = copy_cached_models()
                self.set_status(f"模型已准备：{dest}")
            except Exception as exc:
                self.set_status(f"模型复制失败：{exc}")
        threading.Thread(target=worker, daemon=True).start()

    def load_provider_form(self, event=None) -> None:
        index = self._selected_index(self.provider_list)
        if index is None:
            return
        self.provider_index = index
        provider = self.config.providers[index]
        self.provider_name_var.set(provider.get("name", ""))
        self.provider_base_var.set(provider.get("base_url", ""))
        self.provider_model_var.set(provider.get("model", ""))
        self.provider_key_var.set(provider.get("api_key", ""))

    def add_provider(self) -> None:
        self.config.providers.append({"id": uuid.uuid4().hex, "name": "新供应商", "base_url": "", "model": "", "api_key": ""})
        self.show_providers()

    def delete_provider(self) -> None:
        if len(self.config.providers) <= 1:
            messagebox.showwarning("语言转写", "至少保留一个供应商。")
            return
        index = self._selected_index(self.provider_list)
        if index is None:
            return
        removed = self.config.providers.pop(index)
        if self.config.ai_provider == removed.get("id"):
            self.config.ai_provider = self.config.providers[0]["id"]
        save_config(self.config)
        self.show_providers()

    def save_provider(self) -> None:
        provider = self.config.providers[self.provider_index]
        provider["name"] = self.provider_name_var.get().strip() or "未命名"
        provider["base_url"] = self.provider_base_var.get().strip()
        provider["model"] = self.provider_model_var.get().strip()
        provider["api_key"] = self.provider_key_var.get().strip()
        self.config.ai_provider = provider["id"]
        self.config.deepseek_base_url = provider["base_url"]
        self.config.deepseek_model = provider["model"]
        self.config.deepseek_api_key = provider["api_key"]
        save_config(self.config)
        self.set_status("AI 供应商已保存")
        self.show_providers()

    def load_prompt_form(self, event=None) -> None:
        index = self._selected_index(self.prompt_list)
        if index is None:
            return
        self.prompt_index = index
        prompt = self.config.prompts[index]
        self.prompt_name_var.set(prompt.get("name", ""))
        self.prompt_tag_var.set(prompt.get("tag", ""))
        self.prompt_text.delete("1.0", "end")
        self.prompt_text.insert("1.0", prompt.get("prompt", ""))

    def add_prompt(self) -> None:
        self.config.prompts.append({"id": uuid.uuid4().hex, "name": "新提示词", "tag": "自定义", "prompt": ""})
        self.show_prompts()

    def delete_prompt(self) -> None:
        if len(self.config.prompts) <= 1:
            messagebox.showwarning("语言转写", "至少保留一个提示词。")
            return
        index = self._selected_index(self.prompt_list)
        if index is None:
            return
        removed = self.config.prompts.pop(index)
        if self.config.active_prompt_id == removed.get("id"):
            self.config.active_prompt_id = self.config.prompts[0]["id"]
        save_config(self.config)
        self.show_prompts()

    def save_prompt(self) -> None:
        prompt = self.config.prompts[self.prompt_index]
        prompt["name"] = self.prompt_name_var.get().strip() or "未命名"
        prompt["tag"] = self.prompt_tag_var.get().strip() or "自定义"
        prompt["prompt"] = self.prompt_text.get("1.0", "end").strip()
        self.config.active_prompt_id = prompt["id"]
        self.config.system_prompt = prompt["prompt"]
        save_config(self.config)
        self.set_status("提示词已保存")
        self.show_prompts()

    def load_rule_form(self, event=None) -> None:
        index = self._selected_index(self.rule_list)
        if index is None:
            return
        self.rule_index = index
        rule = self.config.replacement_rules[index]
        self.rule_from_var.set(rule.get("from", ""))
        self.rule_to_var.set(rule.get("to", ""))
        self.rule_enabled_var.set(bool(rule.get("enabled", True)))

    def add_rule(self) -> None:
        self.config.replacement_rules.append({"from": "", "to": "", "enabled": True})
        self.show_dictionary()

    def delete_rule(self) -> None:
        index = self._selected_index(self.rule_list)
        if index is None:
            return
        self.config.replacement_rules.pop(index)
        save_config(self.config)
        self.show_dictionary()

    def save_rule(self) -> None:
        rule = self.config.replacement_rules[self.rule_index]
        rule["from"] = self.rule_from_var.get()
        rule["to"] = self.rule_to_var.get()
        rule["enabled"] = self.rule_enabled_var.get()
        save_config(self.config)
        self.set_status("替换词典已保存")
        self.show_dictionary()

    def _selected_index(self, listbox: tk.Listbox) -> int | None:
        selected = listbox.curselection()
        if not selected:
            return 0 if listbox.size() else None
        return int(selected[0])

    def register_hotkey(self) -> None:
        self.hotkey_error = ""
        try:
            import keyboard
        except ImportError:
            self.hotkey_error = "缺少 keyboard 依赖"
            return
        try:
            keyboard.unhook_all()
            key = (self.config.hotkey or "F2").lower()
            if self.config.hold_to_record:
                keyboard.on_press_key(key, lambda event: self.after(0, self.start_recording), suppress=False)
                keyboard.on_release_key(key, lambda event: self.after(0, self.stop_recording), suppress=False)
            else:
                keyboard.add_hotkey(key, lambda: self.after(0, self.toggle_recording))
        except Exception as exc:
            self.hotkey_error = str(exc)

    def toggle_recording(self) -> None:
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self) -> None:
        if self.recording:
            return
        try:
            self.recorder.start()
            self.recording = True
            self.record_started_at = time.time()
            self.show_recording_indicator()
            self.set_status("正在录音...")
        except Exception as exc:
            self.set_status(f"录音失败：{exc}")
            messagebox.showerror("录音失败", str(exc))

    def stop_recording(self) -> None:
        if not self.recording:
            return
        try:
            wav_path = self.recorder.stop()
            self.recording = False
            self.hide_recording_indicator()
            elapsed = time.time() - self.record_started_at
            self.set_status(f"录音完成 {elapsed:.1f}s，正在转写...")
            self.process_audio(wav_path)
        except Exception as exc:
            self.recording = False
            self.hide_recording_indicator()
            self.set_status(f"停止录音失败：{exc}")
            messagebox.showerror("停止录音失败", str(exc))

    def choose_audio(self) -> None:
        audio = filedialog.askopenfilename(
            title="选择音频文件",
            filetypes=[("Audio", "*.wav *.mp3 *.m4a *.aac *.flac"), ("All files", "*.*")],
        )
        if audio:
            self.process_audio(Path(audio))

    def polish_clipboard(self) -> None:
        try:
            raw = read_clipboard()
        except Exception as exc:
            messagebox.showerror("读取剪贴板失败", str(exc))
            return
        self.process_text(raw, "clipboard")

    def process_audio(self, audio_path: Path) -> None:
        def worker() -> None:
            try:
                raw = transcribe_audio(audio_path, self.config)
                self.process_text(raw, str(audio_path), from_worker=True)
            except Exception as exc:
                self.set_status(f"转写失败：{exc}")
        threading.Thread(target=worker, daemon=True).start()

    def process_text(self, raw: str, source: str, from_worker: bool = False) -> None:
        def worker() -> None:
            normalized = normalize_text(raw, self.config)
            polished = ""
            try:
                polished = polish_text(normalized, self.config)
            except Exception as exc:
                polished = normalized
                self.set_status(f"AI 优化跳过：{exc}")

            output = choose_output(raw, normalized, polished, self.config)
            if self.config.copy_result_to_clipboard:
                clipboard_text = raw if self.config.keep_raw_clipboard else output
                self.after(0, lambda value=clipboard_text: write_clipboard(value))
            if self.config.save_history:
                append_history(raw, output, source)
            if self.config.auto_paste:
                self.after(250, self.send_paste)
            self.after(0, lambda: self.fill_outputs(raw, normalized, output))
            self.set_status("完成，最终稿已生成")

        if from_worker:
            worker()
        else:
            threading.Thread(target=worker, daemon=True).start()

    def fill_outputs(self, raw: str, normalized: str, final: str) -> None:
        if not hasattr(self, "raw_text"):
            self.show_home()
        for widget, value in [(self.raw_text, raw), (self.normalized_text, normalized), (self.final_text, final)]:
            widget.delete("1.0", "end")
            widget.insert("1.0", value)

    def copy_final_text(self) -> None:
        if not hasattr(self, "final_text"):
            return
        text = self.final_text.get("1.0", "end").strip()
        if text:
            write_clipboard(text)
            self.set_status("最终稿已复制")

    def show_recording_indicator(self) -> None:
        if not self.config.show_floating_indicator or self.float_window is not None:
            return
        win = tk.Toplevel(self)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#1f2937")
        label = tk.Label(win, text="● 录音中", bg="#1f2937", fg="#ffffff", padx=18, pady=10, font=("Microsoft YaHei UI", 11, "bold"))
        label.pack()
        x = self.winfo_screenwidth() - 180
        y = 80
        win.geometry(f"+{x}+{y}")
        self.float_window = win

    def hide_recording_indicator(self) -> None:
        if self.float_window is not None:
            self.float_window.destroy()
            self.float_window = None

    def send_paste(self) -> None:
        try:
            import keyboard

            keyboard.send("ctrl+v")
        except Exception as exc:
            self.set_status(f"自动粘贴失败：{exc}")

    def on_close(self) -> None:
        try:
            import keyboard

            keyboard.unhook_all()
        except Exception:
            pass
        self.destroy()


def run_gui() -> None:
    app = TranscriberApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    paths = resolve_model_paths(app.config)
    provider = get_active_provider(app.config) or {}
    prompt = get_active_prompt(app.config) or {}
    app.set_status(f"模型：{paths.root.name} / AI：{provider.get('name', '未配置')} / 提示词：{prompt.get('name', '未配置')}")
    app.mainloop()
