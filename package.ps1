$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Assert-ExitCode {
  param(
    [string]$Step,
    [int]$ExitCode
  )
  if ($ExitCode -ne 0) {
    throw "$Step failed with exit code $ExitCode"
  }
}

if (-not (Test-Path ".build-venv\Scripts\python.exe")) {
  python -m venv .build-venv
  Assert-ExitCode "Create isolated build environment" $LASTEXITCODE
}
.\.build-venv\Scripts\python.exe -m pip install --upgrade "pip>=26.1.2" "setuptools>=81,<82" wheel
Assert-ExitCode "Update build tools" $LASTEXITCODE
.\.build-venv\Scripts\python.exe -m pip install --upgrade -r requirements.txt "pyinstaller>=6.21,<7"
Assert-ExitCode "Install build dependencies" $LASTEXITCODE
.\.build-venv\Scripts\python.exe -m PyInstaller `
  --name "YuyanZhuanxie" `
  --noconsole `
  --clean `
  --noconfirm `
  --specpath "build" `
  --exclude-module "torch" `
  --exclude-module "torchaudio" `
  --exclude-module "transformers" `
  --exclude-module "funasr" `
  --hidden-import "funasr_onnx.paraformer_bin" `
  --hidden-import "funasr_onnx.vad_bin" `
  --hidden-import "funasr_onnx.punc_bin" `
  --add-data "$PSScriptRoot\NOTICE;." `
  --add-data "$PSScriptRoot\LICENSE;." `
  app_launcher.py
Assert-ExitCode "Build Windows EXE" $LASTEXITCODE

Write-Host "Build completed: dist\YuyanZhuanxie\YuyanZhuanxie.exe"
Write-Host "Models and config.json are not bundled. Configure them separately."
