param(
    [string]$Python = "py -3.14",
    [string]$VenvPath = ".venv"
)

$ErrorActionPreference = "Stop"
$pythonParts = $Python -split " "
& $pythonParts[0] $pythonParts[1] -c "import sys; assert sys.version_info[:2] == (3, 14), sys.version; print(sys.executable)"
& $pythonParts[0] $pythonParts[1] -m venv $VenvPath
$venvPython = Join-Path $VenvPath "Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt
& $venvPython scripts\check_environment.py
Write-Host "SciPlot environment is ready at $VenvPath. Origin 2022 and its Python installation were not modified."
