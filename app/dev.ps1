# Desktop 開發入口；只對本次 process 設定工具鏈，不修改系統 PATH。
[CmdletBinding()]
param([switch]$Build, [switch]$Test)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$cargo=Join-Path $root 'artifacts/desktop-toolchain/cargo'
if (Test-Path -LiteralPath (Join-Path $cargo 'bin/cargo.exe')) {
    $env:CARGO_HOME=$cargo
    $env:RUSTUP_HOME=Join-Path $root 'artifacts/desktop-toolchain/rustup'
    $env:PATH="$(Join-Path $cargo 'bin');$env:PATH"
}
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {throw '缺少 Rust MSVC toolchain；請依 docs/specs/app-architecture.md 準備。'}
Push-Location $PSScriptRoot
try {
    if ($Test) {
        & npm.cmd run test:contracts
        if ($LASTEXITCODE -ne 0) {throw 'Contract tests failed'}
        & python (Join-Path $root 'services/engines/test_runner_service.py')
        if ($LASTEXITCODE -ne 0) {throw 'Adapter boundary tests failed'}
        & python (Join-Path $root 'services/engines/test_seed_cache.py')
        if ($LASTEXITCODE -ne 0) {throw 'Cache repair safety tests failed'}
        Push-Location $root
        try {
            & (Join-Path $root 'tools/venvs/seed-vc/Scripts/python.exe') -m unittest services.tts.test_service services.tts.test_snapshot services.tts.test_validation
            if ($LASTEXITCODE -ne 0) {throw 'TTS lifecycle tests failed'}
        } finally {Pop-Location}
        Push-Location src-tauri
        try { & cargo test --lib; if ($LASTEXITCODE -ne 0) {throw 'Rust process tests failed'} } finally {Pop-Location}
    } elseif ($Build) {
        & npm.cmd run tauri -- build --debug --no-bundle
        if ($LASTEXITCODE -ne 0) {throw 'Desktop build failed'}
        $builtExe=Join-Path $PSScriptRoot 'src-tauri/target/debug/aethertune-desktop.exe'
        $entryExe=Join-Path $root 'AetherTune.exe'
        if (-not (Test-Path -LiteralPath $builtExe -PathType Leaf)) {throw "找不到 Desktop build 輸出：$builtExe"}
        Copy-Item -LiteralPath $builtExe -Destination $entryExe -Force
        if ((Get-FileHash -LiteralPath $builtExe -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $entryExe -Algorithm SHA256).Hash) {
            throw '根目錄 AetherTune.exe 與 build 輸出 hash 不一致'
        }
        Write-Host "Desktop 入口：$entryExe"
    }
    else { & npm.cmd run tauri dev; if ($LASTEXITCODE -ne 0) {throw 'Desktop dev failed'} }
} finally {Pop-Location}
