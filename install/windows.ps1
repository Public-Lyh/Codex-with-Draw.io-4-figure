# Run from PowerShell: .\install\windows.ps1
# All arguments (for example --agents codex,claude) are forwarded to Python.
$ErrorActionPreference = 'Stop'
$workflowArgs = @($args)
$repoDir = Split-Path -Parent $PSScriptRoot
if ($env:OS -ne 'Windows_NT') { throw 'Use this entrypoint on Windows.' }

function Find-WorkflowPython {
    if ($env:DRAWIO_PYTHON) {
        & $env:DRAWIO_PYTHON -c 'import sys, venv; assert sys.version_info >= (3,10)' 2>$null
        if ($LASTEXITCODE -eq 0) { return $env:DRAWIO_PYTHON }
        throw 'DRAWIO_PYTHON must point to a working Python 3.10+ executable.'
    }
    $candidates = @()
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        $resolved = & $launcher.Source -3 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0) { $candidates += $resolved }
    }
    $pythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCmd -and $pythonCmd.Source -notlike '*\WindowsApps\*') { $candidates += $pythonCmd.Source }
    foreach ($base in @("$env:LOCALAPPDATA\Programs\Python", "$env:ProgramFiles\Python")) {
        if (Test-Path $base) {
            $candidates += @(Get-ChildItem -Path "$base\Python*\python.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object FullName)
        }
    }
    foreach ($candidate in $candidates) {
        try {
            & $candidate -c 'import sys, venv; assert sys.version_info >= (3,10)' 2>$null
            if ($LASTEXITCODE -eq 0) { return $candidate }
        } catch { continue }
    }
    return $null
}

try {
    $workflowPython = Find-WorkflowPython
    if (-not $workflowPython) {
        Write-Host 'Python 3.10+ is required. Install Python 3.12 using winget?'
        if ($workflowArgs -notcontains '--yes') {
            $reply = Read-Host '[Y/n]'
            if ($reply -match '^(n|no)$') { throw 'Install Python 3.10+ and run again.' }
        }
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw 'winget not found. Install Microsoft App Installer or use docs/windows.md.' }
        & winget install --exact --id Python.Python.3.12 --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity
        if ($LASTEXITCODE -ne 0) { throw "Python installation failed: $LASTEXITCODE" }
        $workflowPython = Find-WorkflowPython
        if (-not $workflowPython) { throw 'Reopen PowerShell or set DRAWIO_PYTHON to the installed python.exe.' }
    }
    & $workflowPython "$repoDir\scripts\setup_workflow.py" @workflowArgs
    exit $LASTEXITCODE
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
