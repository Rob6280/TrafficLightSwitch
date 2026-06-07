param(
    [string]$PythonCommand = "python"
)

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

& $PythonCommand -m venv .venv
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Virtual environment is ready."
Write-Host "Activate it with: .\.venv\Scripts\Activate.ps1"
Write-Host "Run the program with: python Lights.py"
