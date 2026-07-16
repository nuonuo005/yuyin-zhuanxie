# 语言转写（Yuyin Zhuanxie）

> 按住热键说话，松开自动转写 + AI 润色，直接粘贴到任何输入框。

一个 Windows 桌面语音转写工具，基于本地 FunASR 模型实现中文语音识别，配合 DeepSeek 等大模型进行智能书面化整理，让口语秒变正式文本。

## v1.3.0 更新摘要

- 录音改为边录边写临时 WAV，降低长时间录音的内存占用。
- 转写完成后自动清理临时录音，并增加最长录音时间保护。
- 增加处理状态锁和单实例保护，避免重复转写、重复请求和热键冲突。
- DeepSeek 默认模型更新为 `deepseek-v4-flash`，完善超时、限流、鉴权失败和返回截断处理。
- API Key 使用 Windows DPAPI 加密，配置采用安全替换和备份恢复。
- 剪贴板改用 Windows 原生接口，失败时不再继续自动粘贴。
- 历史记录默认限制为 5000 条，避免长期使用后文件无限增长。
- 精简未使用的 PyTorch、Torchaudio、Transformers 和完整版 FunASR 依赖。
- 修复安装和打包脚本可能在实际失败后仍提示成功的问题。
- 新增 10 项自动测试，并完成真实本地转写、源码启动和 EXE 启动验证。

完整更新记录见 [CHANGELOG.md](CHANGELOG.md)。

## 核心功能

- **🎤 热键录音** — 默认 `F2`，支持按住录音/松开转写，也可切换为切换模式
- **🧠 本地 ASR** — 基于 FunASR ONNX，离线运行 Paraformer 中文语音识别 + VAD 语音端点检测 + 标点恢复，无需联网
- **✨ AI 书面化** — 自动识别口语中的自我修正（如"算了""改成""不不不"），修正同音错别字，输出通顺的书面文本
- **📋 一键输出** — 转写结果自动复制到剪贴板，支持自动粘贴到当前窗口
- **🖥️ 可视化桌面客户端** — 提供 GUI 界面，可切换录音模式、管理提示词和配置 AI 供应商
- **🔧 提示词管理** — 内置「书面整理」「会议纪要」「消息回复」三种模板，支持自定义增删
- **📝 替换词典** — 自定义错词自动替换，支持启用/禁用单个规则
- **⚡ 开机自启** — 支持设置为开机自动启动，常驻后台
- **🖥️ 命令行模式** — 支持 `doctor`（环境检测）、`transcribe`（纯转写）、`run`（转写+AI）、`polish-clipboard`（仅润色剪贴板）
- **📦 打包 EXE** — 一键打包为独立 exe 文件分发给他人使用

## 工作流程

```
按下热键 → 录音中 → 松开热键 → 本地 ASR 转写 → AI 书面化润色 → 复制到剪贴板/自动粘贴
```

## 技术栈

本项目使用了以下优秀的开源技术：

| 组件 | 技术 | 说明 |
|------|------|------|
| 语音识别 | [FunASR](https://github.com/modelscope/FunASR) / [Paraformer](https://modelscope.cn/models/iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-onnx) | 阿里达摩院开源的中文语音识别模型 |
| 语音端点检测 | [FSMN-VAD](https://modelscope.cn/models/iic/speech_fsmn_vad_zh-cn-16k-common-onnx) | 自动检测语音起止，去除静音 |
| 标点恢复 | [CT-Transformer](https://modelscope.cn/models/iic/punc_ct-transformer_zh-cn-common-vocab272727-onnx) | 自动添加标点符号 |
| 运行时 | [funasr-onnx](https://pypi.org/project/funasr-onnx/) | FunASR 的 ONNX 推理运行时 |
| AI 润色 | [DeepSeek API](https://platform.deepseek.com/) | 默认 AI 供应商，兼容 OpenAI 格式 API |

> 以上模型均来自 [ModelScope](https://modelscope.cn) 公开模型仓库，遵循各自的开放协议。感谢这些开源项目的贡献！

## 模型获取

本工具需要以下三个 ONNX 模型（需用户自行下载到 `.local_models/iic/` 目录）：

```
.local_models/iic/
├── speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-onnx/
├── speech_fsmn_vad_zh-cn-16k-common-onnx/
└── punc_ct-transformer_zh-cn-common-vocab272727-onnx/
```

**方式一：运行项目命令自动准备（推荐）**

运行 `.\语言转写.bat init-models`。程序会优先复制本机缓存；缓存不存在时，会从 ModelScope 下载。

**方式二：手动从 ModelScope 下载**

访问 [ModelScope 模型页面](https://modelscope.cn/models?filter=funasr) 分别下载上述三个模型，放入 `.local_models/iic/` 目录。

**方式三：从缓存中复制**

如果你本地已通过其他 FunASR 应用下载过模型，通常缓存路径为：

```
C:\Users\<用户名>\.cache\modelscope\hub\models\iic\
```

直接复制到项目 `.local_models/iic/` 即可。

## 安装部署

### 环境要求

- Windows 10/11
- Python 3.10+
- 可正常访问 DeepSeek API（或自备 OpenAI-compatible API）

### 安装步骤

```powershell
# 1. 克隆项目
git clone git@github.com:nuonuo005/yuyin-zhuanxie.git
cd yuyin-zhuanxie

# 2. 运行安装脚本（创建虚拟环境并安装依赖）
.\install.ps1

# 如果 PowerShell 阻止脚本运行，先执行：
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1
```

### 配置

```powershell
# 复制配置模板
Copy-Item config.example.json config.json
```

编辑 `config.json`，填入你的 DeepSeek API Key（或配置其他兼容供应商）：

```json
{
  "deepseek_api_key": "你的API Key",
  "deepseek_base_url": "https://api.deepseek.com/v1",
  "deepseek_model": "deepseek-v4-flash",
  "model_root": ".local_models/iic"
}
```

主要配置项说明：

| 配置项 | 说明 |
|--------|------|
| `deepseek_api_key` | DeepSeek API 密钥 |
| `providers` | AI 供应商列表，支持添加多个 |
| `prompts` | 提示词模板，可自定义 |
| `hotkey` | 录音热键，默认 `F2` |
| `hold_to_record` | `true` 按住录音 / `false` 切换模式 |
| `output_mode` | `polished` 书面化 / `normalized` 规则整理 / `raw` 原始转写 |
| `replacement_rules` | 替换词典 |
| `auto_paste` | 是否自动粘贴 |
| `start_minimized` | 是否启动时最小化到托盘 |
| `max_recording_seconds` | 单次录音最长时间，默认 600 秒 |
| `history_max_entries` | 历史记录最多保留条数，默认 5000 条 |

API Key 保存时会使用 Windows 自带的数据保护功能加密。加密后的配置只能由当前电脑的当前 Windows 用户解密；迁移到其他电脑后需要重新填写 API Key。

## 使用方式

### GUI 模式（推荐）

```powershell
# 无命令行窗口启动
.\语言转写.vbs

# 语言转写.bat 主要用于命令行检查和排错
```

### 命令行模式

```powershell
# 环境检测
.\语言转写.bat doctor

# 转写音频文件
.\语言转写.bat transcribe "demo.wav"

# 转写 + AI 书面化
.\语言转写.bat run "demo.wav"

# 仅润色剪贴板中的文本
.\语言转写.bat polish-clipboard
```

### 打包为 EXE

```powershell
.\package.ps1
```

产物在 `dist\YuyanZhuanxie\YuyanZhuanxie.exe`。

注意：

- 分发时需要复制整个 `dist\YuyanZhuanxie\` 文件夹，不能只复制其中的 EXE。
- 本地语音模型和个人 `config.json` 不会被打包。
- 新电脑首次运行时需要准备模型，并由使用者自行填写 API Key。
- 当前完整打包目录体积较大，主要来自离线语音识别和数值计算运行库。

## 发布前检查

```powershell
.\.venv\Scripts\python.exe -m unittest discover
.\.venv\Scripts\python.exe -m pip check
.\语言转写.bat doctor
.\package.ps1
```

本项目已确认 `config.json`、模型、虚拟环境、历史记录和构建产物均由 `.gitignore` 排除。

## 开源说明

本项目代码完全开源，遵循 LICENSE 中的许可协议。可以自由使用、修改和分发。

**请勿提交以下内容到仓库：**

- `.venv/` — Python 虚拟环境
- `.local_models/` — 本地模型文件
- `config.json` — 包含 API Key 的配置文件
- `history.jsonl` — 转写历史记录
- 任何 API Key 或密钥

FunASR / ModelScope 模型请按其各自的公开协议使用，详见 `NOTICE` 文件中的来源说明。

## License

本项目代码采用 MIT 协议开源，详见 [LICENSE](LICENSE)。所依赖的开源模型遵循各自的许可证。
