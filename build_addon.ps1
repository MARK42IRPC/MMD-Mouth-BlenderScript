param(
    [string]$Python = "",
    [string]$OutputDirectory = "",
    [switch]$SkipWorkerBuild
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $repoRoot "dist-addon"
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

if (-not $SkipWorkerBuild) {
    $workerScript = Join-Path $repoRoot "build_worker.ps1"
    if ($Python) {
        & $workerScript -Python $Python
    } else {
        & $workerScript
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Worker build failed"
    }
}

$workerExecutable = Join-Path `
    $repoRoot `
    "mmd_mouth\runtime\mmd_mouth_worker\mmd_mouth_worker.exe"
if (-not (Test-Path -LiteralPath $workerExecutable -PathType Leaf)) {
    throw "Packaged worker is missing: $workerExecutable"
}

$stagingRoot = Join-Path $OutputDirectory "staging"
$stagingPackage = Join-Path $stagingRoot "mmd_mouth"
if (Test-Path -LiteralPath $stagingRoot) {
    Remove-Item -LiteralPath $stagingRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null
$sourcePackage = Join-Path $repoRoot "mmd_mouth"
New-Item -ItemType Directory -Force -Path $stagingPackage | Out-Null
Get-ChildItem -LiteralPath $sourcePackage -Recurse -File |
    Where-Object {
        $_.FullName -notmatch "\\__pycache__\\" -and
        $_.Extension -ne ".pyc"
    } |
    ForEach-Object {
        $relativePath = $_.FullName.Substring($sourcePackage.Length + 1)
        $destination = Join-Path $stagingPackage $relativePath
        $destinationDirectory = Split-Path -Parent $destination
        New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $destination
    }

$bundledModelNames = @(
    "vosk-model-small-cn-0.22.zip",
    "vosk-model-small-ja-0.22.zip",
    "vosk-model-small-en-us-0.15.zip"
)
$bundledModelDirectory = Join-Path $stagingPackage "resources\vosk"
New-Item -ItemType Directory -Force -Path $bundledModelDirectory | Out-Null
foreach ($modelName in $bundledModelNames) {
    $modelSource = Join-Path $repoRoot $modelName
    if (-not (Test-Path -LiteralPath $modelSource -PathType Leaf)) {
        throw "Bundled Vosk model archive is missing: $modelSource"
    }
    Copy-Item `
        -LiteralPath $modelSource `
        -Destination (Join-Path $bundledModelDirectory $modelName)
}

$archivePath = Join-Path $OutputDirectory "MMDmouth-0.5.0.zip"
if (Test-Path -LiteralPath $archivePath) {
    Remove-Item -LiteralPath $archivePath -Force
}
try {
    Compress-Archive `
        -Path $stagingPackage `
        -DestinationPath $archivePath `
        -CompressionLevel Optimal
} finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}

Write-Host "Blender add-on archive created: $archivePath"
