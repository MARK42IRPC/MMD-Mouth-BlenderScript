param(
    [string]$Python = "",
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $Python) {
    $Python = Join-Path $repoRoot ".venv-worker\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Worker Python was not found: $Python"
}

if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $repoRoot "build-worker"
}

$distDirectory = Join-Path $OutputDirectory "dist"
$workDirectory = Join-Path $OutputDirectory "work"
$specDirectory = Join-Path $OutputDirectory "spec"
$addonRuntimeDirectory = Join-Path $repoRoot "mmd_mouth\runtime\mmd_mouth_worker"

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
if (Test-Path -LiteralPath $distDirectory) {
    Remove-Item -LiteralPath $distDirectory -Recurse -Force
}
if (Test-Path -LiteralPath $workDirectory) {
    Remove-Item -LiteralPath $workDirectory -Recurse -Force
}
if (Test-Path -LiteralPath $specDirectory) {
    Remove-Item -LiteralPath $specDirectory -Recurse -Force
}

& $Python -m pip install -r (Join-Path $repoRoot "requirements-worker.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Could not install worker dependencies"
}

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --noupx `
    --name mmd_mouth_worker `
    --collect-all vosk `
    --collect-all pypinyin `
    --collect-all cmudict `
    --collect-data pyopenjtalk `
    --collect-binaries pyopenjtalk `
    --collect-submodules pyopenjtalk `
    --additional-hooks-dir (Join-Path $repoRoot "packaging-hooks") `
    --exclude-module sudachidict_core `
    --distpath $distDirectory `
    --workpath $workDirectory `
    --specpath $specDirectory `
    (Join-Path $repoRoot "worker_entry.py")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed"
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $addonRuntimeDirectory) | Out-Null
if (Test-Path -LiteralPath $addonRuntimeDirectory) {
    Remove-Item -LiteralPath $addonRuntimeDirectory -Recurse -Force
}
Copy-Item `
    -LiteralPath (Join-Path $distDirectory "mmd_mouth_worker") `
    -Destination $addonRuntimeDirectory `
    -Recurse

Write-Host "Bundled worker copied to: $addonRuntimeDirectory"
