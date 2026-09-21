[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'vcclient-rvc-chunk-validation.ps1')

function New-F32Bytes([float]$Value) {
    $bytes = [byte[]]::new(4)
    [Buffer]::BlockCopy([float[]]@($Value), 0, $bytes, 0, 4)
    return $bytes
}

function Assert-ChunkCase([string]$Label, [byte[]]$Bytes, [bool]$ExpectedValid, [string]$ExpectedReason) {
    $result = Test-VcClientChunkResponse $Bytes
    if ($result.valid -ne $ExpectedValid -or $result.reason -ne $ExpectedReason) {
        throw "回歸失敗：$Label valid=$($result.valid) reason=$($result.reason)"
    }
    Write-Output "PASS chunk validation $Label ($($result.reason))"
}

Assert-ChunkCase 'empty' ([byte[]]::new(0)) $false 'empty'
Assert-ChunkCase 'short' ([byte[]](0, 0, 0)) $false 'short'
Assert-ChunkCase 'unaligned' ([byte[]](0, 0, 0, 0, 0)) $false 'unaligned'
Assert-ChunkCase 'all-zero' (New-F32Bytes 0.0) $false 'all_zero'
Assert-ChunkCase 'finite-nonzero' (New-F32Bytes 0.25) $true 'finite_nonzero'
Assert-ChunkCase 'nan' (New-F32Bytes ([float]::NaN)) $false 'nonfinite'
Assert-ChunkCase 'infinity' (New-F32Bytes ([float]::PositiveInfinity)) $false 'nonfinite'

Write-Output 'PASS VCClient RVC chunk validation regression'
