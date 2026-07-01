# 语言转写

一个可二次开发的 Windows 桌面客户端：

```txt
热键录音 -> 本地 FunASR/Paraformer 中文转写 -> AI 书面化 -> 复制到剪贴板/自动粘贴
```

本项目不复制 VocoType 私有代码。它只复用你电脑里已经缓存的同源公开 FunASR / ModelScope ONNX 模型，或让用户自行从官方来源下载同名模型。

## 已实现

- 可视化桌面客户端：双击 `语言转写.bat` 打开。
- 本地 ASR：`funasr-onnx` 直连 Paraformer + VAD + 标点模型。
- AI 供应商管理：DeepSeek 默认，兼容 OpenAI-compatible API。
- 提示词管理：可新增、删除、设置默认提示词。
- 热键设置：默认 `F2`，支持按住录音/松开转写。
- 文本输出设置：复制到剪贴板、自动粘贴、历史记录、输出模式。
- 替换词典：识别错词自动替换。
- 开机自启动：通过 Windows 启动文件夹创建 bat。
- 命令行模式：保留 `doctor`、`transcribe`、`run`、`polish-clipboard`。

## 模型目录

VocoType 当前下载的 ModelScope 模型通常在：

```txt
C:\Users\Administrator\.cache\modelscope\hub\models\iic\
```

本工具默认复制到项目内：

```txt
.local_models/iic/
```

需要包含：

```txt
speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-onnx
speech_fsmn_vad_zh-cn-16k-common-onnx
punc_ct-transformer_zh-cn-common-vocab272727-onnx
```

## 安装

```powershell
cd "E:\AI linshi\语言转写"
.\install.ps1
```

如果 PowerShell 阻止脚本运行，可以先执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1
```

## 使用

打开 GUI（普通用户入口，无命令行黑窗口）：

```powershell
.\语言转写.vbs
```

开发排错入口：

```powershell
.\语言转写.bat doctor
```

检查环境：

```powershell
.\语言转写.bat doctor
```

转写音频文件：

```powershell
.\语言转写.bat transcribe "demo.wav"
```

转写并 AI 书面化：

```powershell
.\语言转写.bat run "demo.wav"
```

只把剪贴板里的口语文本交给 AI 书面化：

```powershell
.\语言转写.bat polish-clipboard
```

## 配置

第一次运行 GUI 后会自动读取默认配置。也可以手动复制：

```powershell
Copy-Item config.example.json config.json
```

重点配置项：

- `providers`：AI 供应商列表，默认 DeepSeek。
- `prompts`：提示词模板。
- `hotkey`：录音热键。
- `model_root`：本地模型目录。
- `output_mode`：`polished` 最终书面稿、`normalized` 规则整理、`raw` 原始转写。
- `replacement_rules`：替换词典。

## 给别人使用

推荐分发方式：

1. 提交源码到 GitHub。
2. 不提交 `.venv/`、`.local_models/`、`config.json`、`history.jsonl`。
3. 用户克隆后运行 `install.ps1`。
4. 用户自行复制或下载官方模型。
5. 用户在 GUI 的“AI 供应商”里填写自己的 API Key。

打包 exe：

```powershell
.\package.ps1
```

打包产物在：

```txt
dist\YuyanZhuanxie\YuyanZhuanxie.exe
```

## 开源边界

可以开源：

- 本项目代码。
- 安装脚本、配置示例、NOTICE、README。

不要提交：

- `.local_models/`
- `.venv/`
- `config.json`
- `history.jsonl`
- 任何 API Key
- VocoType 程序文件或私有 DLL

模型请按 FunASR / ModelScope 的公开模型协议使用，并保留 `NOTICE` 中的来源说明。
