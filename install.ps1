$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m yuyin_zhuanxie init-models
.\.venv\Scripts\python.exe -m yuyin_zhuanxie doctor
