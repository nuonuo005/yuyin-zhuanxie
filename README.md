# 语言转写（Yuyin Zhuanxie）

> 按住热键说话，松开自动转写 + AI 润色，直接粘贴到任何输入框。

一个 Windows 桌面语音转写工具，基于本地 FunASR 模型实现中文语音识别，配合 DeepSeek 等大模型进行智能书面化整理，让口语秒变正式文本。

## 核心功能

- **🎤 热键录音** — 默认 `F3`，支持按住录音/松开转写，也可切换为切换模式
- **🧠 本地 ASR** — 基于 FunASR ONNX，离线运行 Paraformer 中文语音识别 + VAD 语音端点检测 + 标点恢复，无需联网
- **✨ AI 书面化** — 自动识别口语中的自我修正（如"算了""改成""不不不"），修正同音错别字，输出通顺的书面文本
- **📋 一键输出** — 转写结果自动复制到剪贴板，支持自动粘贴到当前窗口
- **🖥️ 可视化桌面客户端** — 提供 GUI 界面，可切换录音模式、管理提示词、配置 AI 供应商、查看历史记录
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

**方式一：通过 funasr-onnx 自动下载（推荐）**

首次运行 GUI 时，程序会自动检测模型是否存在，缺失时会提示下载。

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
  "deepseek_model": "deepseek-chat",
  "model_root": ".local_models/iic"
}
```

主要配置项说明：

| 配置项 | 说明 |
|--------|------|
| `deepseek_api_key` | DeepSeek API 密钥 |
| `providers` | AI 供应商列表，支持添加多个 |
| `prompts` | 提示词模板，可自定义 |
| `hotkey` | 录音热键，默认 `F3` |
| `hold_to_record` | `true` 按住录音 / `false` 切换模式 |
| `output_mode` | `polished` 书面化 / `normalized` 规则整理 / `raw` 原始转写 |
| `replacement_rules` | 替换词典 |
| `auto_paste` | 是否自动粘贴 |
| `start_minimized` | 是否启动时最小化到托盘 |

## 使用方式

### GUI 模式（推荐）

```powershell
# 无命令行窗口启动
.\语言转写.vbs

# 或直接双击 语言转写.bat
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
