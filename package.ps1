$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path ".venv\Scripts\python.exe")) {
  python -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller `
  --name "YuyanZhuanxie" `
  --noconsole `
  --clean `
  --add-data "NOTICE;." `
  --add-data "LICENSE;." `
  app_launcher.py

Write-Host "Build completed: dist\YuyanZhuanxie\YuyanZhuanxie.exe"
Write-Host "Models and config.json are not bundled. Configure them separately."
