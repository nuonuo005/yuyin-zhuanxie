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

if (-not (Test-Path ".venv\Scripts\python.exe")) {
  python -m venv .venv
  Assert-ExitCode "Create virtual environment" $LASTEXITCODE
}
.\.venv\Scripts\python.exe -m pip install --upgrade "pip>=26.1.2" "setuptools>=81,<82" wheel
Assert-ExitCode "Update install tools" $LASTEXITCODE
.\.venv\Scripts\python.exe -m pip install --upgrade -r requirements.txt
Assert-ExitCode "Install project dependencies" $LASTEXITCODE
.\.venv\Scripts\python.exe -m yuyin_zhuanxie init-models
Assert-ExitCode "Prepare local speech models" $LASTEXITCODE
.\.venv\Scripts\python.exe -m yuyin_zhuanxie doctor
Assert-ExitCode "Run environment doctor" $LASTEXITCODE
