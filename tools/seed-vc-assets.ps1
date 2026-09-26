# Shared strict reader/verifier for the Seed-VC asset registry.
# Values observed from local caches are explicitly not treated as upstream provenance.

function Test-SeedVcSafeRelativePath {
    param([object]$Value)

    if ($Value -isnot [string] -or [string]::IsNullOrWhiteSpace($Value)) { return $false }
    if ([IO.Path]::IsPathRooted($Value)) { return $false }
    if ($Value -match '(^|[\\/])\.\.([\\/]|$)' -or $Value -match '(^|[\\/])\.([\\/]|$)') { return $false }
    return $true
}

function Assert-SeedVcAssetRecord {
    param(
        [Parameter(Mandatory)][object]$Record,
        [Parameter(Mandatory)][string]$Context
    )

    if ($Record -isnot [System.Collections.IDictionary]) { throw "$Context must be a JSON object." }
    if (-not (Test-SeedVcSafeRelativePath -Value $Record.path)) { throw "$Context.path must be a safe relative path." }
    $size = $Record.size_bytes
    if ($null -eq $size -or $size -is [bool] -or ($size -isnot [int] -and $size -isnot [long]) -or $size -le 0) {
        throw "$Context.size_bytes must be a positive JSON integer."
    }
    if ($Record.sha256 -isnot [string] -or $Record.sha256 -notmatch '^[0-9a-fA-F]{64}$') {
        throw "$Context.sha256 must be a 64-character hexadecimal digest."
    }
    foreach ($field in @('size_evidence', 'sha256_evidence')) {
        if ($Record[$field] -isnot [string] -or [string]::IsNullOrWhiteSpace($Record[$field])) {
            throw "$Context.$field must identify the evidence level."
        }
    }
}

function ConvertTo-SeedVcManifestValue {
    param([AllowNull()][object]$Value)

    if ($null -eq $Value) { return $null }
    if ($Value -is [System.Collections.IDictionary]) {
        $convertedMap = @{}
        foreach ($key in $Value.Keys) {
            $convertedMap[$key] = ConvertTo-SeedVcManifestValue -Value $Value[$key]
        }
        return ,$convertedMap
    }
    if ($Value -is [System.Array]) {
        $convertedArray = @(
            foreach ($item in $Value) { ConvertTo-SeedVcManifestValue -Value $item }
        )
        return ,$convertedArray
    }
    if ($Value -is [System.Management.Automation.PSCustomObject]) {
        $convertedMap = @{}
        foreach ($property in $Value.PSObject.Properties) {
            $convertedMap[$property.Name] = ConvertTo-SeedVcManifestValue -Value $property.Value
        }
        return ,$convertedMap
    }
    return $Value
}

function Assert-SeedVcExactStringSet {
    param(
        [Parameter(Mandatory)][object[]]$Actual,
        [Parameter(Mandatory)][string[]]$Expected,
        [Parameter(Mandatory)][string]$Context
    )

    if (@($Actual | Where-Object { $_ -isnot [string] }).Count -gt 0) { throw "$Context must contain only strings." }
    $duplicates = @($Actual | Group-Object | Where-Object Count -gt 1)
    $missing = @($Expected | Where-Object { $_ -cnotin $Actual })
    $unexpected = @($Actual | Where-Object { $_ -cnotin $Expected })
    if ($duplicates.Count -gt 0 -or $missing.Count -gt 0 -or $unexpected.Count -gt 0 -or $Actual.Count -ne $Expected.Count) {
        throw "$Context set mismatch (missing: $($missing -join ', '); unexpected: $($unexpected -join ', '); duplicates: $($duplicates.Name -join ', '))."
    }
}

function Read-SeedVcAssetManifest {
    param([Parameter(Mandatory)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Seed-VC asset manifest is missing: $Path" }
    try {
        $jsonObject = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
        $manifest = ConvertTo-SeedVcManifestValue -Value $jsonObject
    }
    catch { throw "Seed-VC asset manifest is invalid JSON: $Path ($($_.Exception.Message))" }
    if ($manifest -isnot [System.Collections.IDictionary]) { throw 'Seed-VC asset manifest root must be a JSON object.' }
    if (($manifest.schema_version -isnot [int] -and $manifest.schema_version -isnot [long]) -or $manifest.schema_version -ne 1) { throw 'Seed-VC asset manifest schema_version must be integer 1.' }
    if ($manifest.clean_machine_bootstrap_status -cne 'WAITING') { throw 'Seed-VC asset manifest must preserve clean_machine_bootstrap_status=WAITING.' }
    if ($manifest.supported_profile_scope -cne 'realtime-tiny' -or
        $manifest.offline_v1_helper_completeness -cne 'WAITING' -or $manifest.offline_v1_scope -cne 'out-of-scope') {
        throw 'Seed-VC asset manifest must scope verified runtime assets to realtime-tiny and preserve offline-v1 helper completeness=WAITING/out-of-scope.'
    }

    $source = $manifest.seed_vc_source
    if ($source -isnot [System.Collections.IDictionary] -or $source.revision -isnot [string] -or
        $source.revision -cne '51383efd921027683c89e5348211d93ff12ac2a8') {
        throw 'Seed-VC source revision must remain the registered official upstream commit 51383efd921027683c89e5348211d93ff12ac2a8.'
    }
    if ($source.repo_url -cne 'https://github.com/Plachtaa/seed-vc' -or $source.license -cne 'GPL-3.0' -or
        $source.revision_evidence_level -cne 'official-upstream-git-commit') {
        throw 'Seed-VC source provenance evidence must remain the pinned official upstream Git commit and GPL-3.0 declaration.'
    }
    if ($source.required_files -isnot [System.Array]) { throw 'Seed-VC source.required_files must be an array.' }
    foreach ($file in $source.required_files) {
        if (-not (Test-SeedVcSafeRelativePath -Value $file)) { throw 'Seed-VC source.required_files contains an unsafe path.' }
    }
    $expectedSourceFiles = @(
        'real-time-gui.py',
        'requirements.txt',
        'configs/presets/config_dit_mel_seed_uvit_xlsr_tiny.yml',
        'configs/hifigan.yml'
    )
    Assert-SeedVcExactStringSet -Actual @($source.required_files) -Expected $expectedSourceFiles -Context 'Seed-VC source.required_files'

    if ($manifest.checkpoints -isnot [System.Array] -or $manifest.checkpoints.Count -ne 2) { throw 'Seed-VC checkpoints must contain exactly the two registered profiles.' }
    $checkpointIds = @()
    foreach ($checkpoint in $manifest.checkpoints) {
        Assert-SeedVcAssetRecord -Record $checkpoint -Context 'checkpoint'
        if ($checkpoint.id -isnot [string] -or $checkpoint.model_repo -cne 'https://huggingface.co/Plachta/Seed-VC' -or
            $checkpoint.model_repo_revision -cne '257283f9f41585055e8f858fba4fd044e5caed6e') {
            throw 'Checkpoint model provenance must remain the pinned official Plachta/Seed-VC commit 257283f9f41585055e8f858fba4fd044e5caed6e.'
        }
        if ($checkpoint.license -cne 'GPL-3.0' -or $checkpoint.evidence_level -cne 'official-model-repository-commit-and-lfs-metadata' -or
            $checkpoint.size_evidence -cne 'official-huggingface-lfs-metadata' -or
            $checkpoint.sha256_evidence -cne 'official-huggingface-lfs-metadata') {
            throw 'Checkpoint license and size/SHA evidence must remain bound to official model repository metadata.'
        }
        $expectedCheckpointPath = switch -CaseSensitive ($checkpoint.id) {
            'offline-v1' { 'models/seed-vc/checkpoints/offline-v1/DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth' }
            'realtime-tiny' { 'models/seed-vc/checkpoints/realtime-tiny/DiT_uvit_tat_xlsr_ema.pth' }
            default { throw "Unknown Seed-VC checkpoint id in manifest: $($checkpoint.id)" }
        }
        if ($checkpoint.path -cne $expectedCheckpointPath) { throw "Checkpoint path/id mapping mismatch for $($checkpoint.id)." }
        $checkpointIds += $checkpoint.id
    }
    if (@($checkpointIds | Select-Object -Unique).Count -ne 2 -or
        @($checkpointIds | Where-Object { $_ -in @('offline-v1', 'realtime-tiny') }).Count -ne 2) {
        throw 'Checkpoint ids must contain exactly one offline-v1 and one realtime-tiny entry.'
    }

    if ($manifest.huggingface_repositories -isnot [System.Array] -or $manifest.huggingface_repositories.Count -ne 3) {
        throw 'huggingface_repositories must contain exactly the three required repositories.'
    }
    $expectedHfRepositories = @{
        'facebook/wav2vec2-xls-r-300m' = @{ cache = 'models--facebook--wav2vec2-xls-r-300m'; revision = '1a640f32ac3e39899438a2931f9924c02f080a54'; files = @('pytorch_model.bin','config.json','preprocessor_config.json') }
        'funasr/campplus' = @{ cache = 'models--funasr--campplus'; revision = 'e4b6ede7ce16997aff4ae69fbca1f0175e2afede'; files = @('campplus_cn_common.bin') }
        'FunAudioLLM/CosyVoice-300M' = @{ cache = 'models--FunAudioLLM--CosyVoice-300M'; revision = '24c40509c3c5ea6fe06b5f8790ff99e3714a6bee'; files = @('hift.pt') }
    }
    $repositoryIds = @($manifest.huggingface_repositories | ForEach-Object { [string]$_.repo_id })
    Assert-SeedVcExactStringSet -Actual $repositoryIds -Expected @($expectedHfRepositories.Keys) -Context 'huggingface_repositories.repo_id'
    foreach ($repository in $manifest.huggingface_repositories) {
        if ($repository -isnot [System.Collections.IDictionary] -or $repository.repo_id -isnot [string]) {
            throw 'Each Hugging Face repository entry must be a JSON object with a string repo_id.'
        }
        $expectedRepository = $expectedHfRepositories[[string]$repository.repo_id]
        if ($null -eq $expectedRepository -or
            -not (Test-SeedVcSafeRelativePath -Value $repository.cache_directory) -or
            $repository.cache_directory -cne $expectedRepository.cache -or
            $repository.expected_local_revision -cne $expectedRepository.revision -or
            $repository.revision_evidence_level -cne 'observed-local-cache' -or
            $repository.upstream_revision_verification -cne 'WAITING' -or $repository.license -isnot [string] -or
            $repository.license -cne 'Apache-2.0' -or $repository.license_evidence_level -cne 'official-model-card' -or
            $repository.files -isnot [System.Array]) {
            throw 'Each Hugging Face repository must declare a local revision pin, evidence level, license, and files.'
        }
        $filePaths = @($repository.files | ForEach-Object { [string]$_.path })
        Assert-SeedVcExactStringSet -Actual $filePaths -Expected $expectedRepository.files -Context "Hugging Face $($repository.repo_id).files"
        foreach ($asset in $repository.files) {
            Assert-SeedVcAssetRecord -Record $asset -Context "Hugging Face $($repository.repo_id) asset"
            if ($asset.size_evidence -cne 'observed-local-cache' -or $asset.sha256_evidence -cne 'observed-local-cache') {
                throw "Hugging Face $($repository.repo_id) asset evidence must remain observed-local-cache."
            }
        }
    }

    $vad = $manifest.model_scope_fsmn_vad
    if ($vad -isnot [System.Collections.IDictionary] -or $vad.model_id -cne 'iic/speech_fsmn_vad_zh-cn-16k-common-pytorch' -or
        $vad.requested_model_revision -cne 'v2.0.4' -or $null -ne $vad.resolved_repository_revision -or
        $vad.license_status -cne 'UNKNOWN' -or $vad.bootstrap_status -cne 'WAITING' -or
        $vad.files -isnot [System.Array] -or $vad.files.Count -ne 4) {
        throw 'FSMN-VAD provenance must remain requested=v2.0.4, resolved revision=null, license UNKNOWN, and bootstrap WAITING.'
    }
    Assert-SeedVcExactStringSet -Actual @($vad.files | ForEach-Object { [string]$_.path }) -Expected @('model.pt','config.yaml','configuration.json','am.mvn') -Context 'ModelScope FSMN-VAD.files'
    foreach ($asset in $vad.files) {
        Assert-SeedVcAssetRecord -Record $asset -Context 'ModelScope FSMN-VAD asset'
        if ($asset.size_evidence -cne 'observed-local-cache' -or $asset.sha256_evidence -cne 'observed-local-cache') {
            throw 'ModelScope FSMN-VAD file integrity evidence must remain observed-local-cache.'
        }
    }
    return $manifest
}

function Test-SeedVcRegisteredFile {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][object]$Asset,
        [Parameter(Mandatory)][string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return "$Label is missing or not a regular file: $Path" }
    $item = Get-Item -LiteralPath $Path -ErrorAction Stop
    if ($item.Length -ne [long]$Asset.size_bytes) {
        return "$Label size mismatch: expected $($Asset.size_bytes) bytes, found $($item.Length): $Path"
    }
    $actualHash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash
    if ($actualHash -ine [string]$Asset.sha256) {
        return "$Label SHA-256 mismatch: expected $($Asset.sha256), found ${actualHash}: $Path"
    }
    return $null
}

function Get-SeedVcAssetManifestFindings {
    param(
        [Parameter(Mandatory)][System.Collections.IDictionary]$Manifest,
        [Parameter(Mandatory)][string]$ProjectRoot,
        [Parameter(Mandatory)][string]$SeedVcRepo,
        [Parameter(Mandatory)][string]$ModelScopeVadPath,
        [string]$RealtimeCheckpointOverride
    )

    $findings = [System.Collections.Generic.List[string]]::new()
    foreach ($relativeFile in $Manifest.seed_vc_source.required_files) {
        $path = Join-Path $SeedVcRepo $relativeFile
        if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Item -LiteralPath $path -ErrorAction SilentlyContinue).Length -le 0) {
            $findings.Add("Seed-VC required source file is missing, not regular, or empty: $relativeFile")
        }
    }
    foreach ($checkpoint in $Manifest.checkpoints) {
        # Current setup and GUI asset gates support only the realtime profile. The
        # offline-v1 metadata is retained for provenance but does not imply a complete
        # offline helper environment or block realtime use when its checkpoint is absent.
        if ($checkpoint.id -cne $Manifest.supported_profile_scope) { continue }
        $path = Join-Path $ProjectRoot $checkpoint.path
        if ($checkpoint.id -ceq 'realtime-tiny' -and $RealtimeCheckpointOverride) { $path = $RealtimeCheckpointOverride }
        $finding = Test-SeedVcRegisteredFile -Path $path -Asset $checkpoint -Label "Seed-VC $($checkpoint.id) checkpoint"
        if ($finding) { $findings.Add($finding) }
    }
    foreach ($repository in $Manifest.huggingface_repositories) {
        $cacheRoot = Join-Path (Join-Path $SeedVcRepo 'checkpoints') $repository.cache_directory
        $refPath = Join-Path $cacheRoot 'refs\main'
        if (-not (Test-Path -LiteralPath $refPath -PathType Leaf)) {
            $findings.Add("Hugging Face refs/main is missing for $($repository.repo_id): $refPath")
            continue
        }
        $actualRevision = (Get-Content -LiteralPath $refPath -Raw -Encoding UTF8).Trim()
        if ($actualRevision -cne $repository.expected_local_revision) {
            $findings.Add("Hugging Face local snapshot revision mismatch for $($repository.repo_id): expected $($repository.expected_local_revision), found $actualRevision")
            continue
        }
        foreach ($asset in $repository.files) {
            $path = Join-Path (Join-Path (Join-Path $cacheRoot 'snapshots') $repository.expected_local_revision) $asset.path
            $finding = Test-SeedVcRegisteredFile -Path $path -Asset $asset -Label "Hugging Face $($repository.repo_id)/$($asset.path)"
            if ($finding) { $findings.Add($finding) }
        }
    }
    foreach ($asset in $Manifest.model_scope_fsmn_vad.files) {
        $path = Join-Path $ModelScopeVadPath $asset.path
        $finding = Test-SeedVcRegisteredFile -Path $path -Asset $asset -Label "ModelScope FSMN-VAD $($asset.path) (local-observed hash; upstream revision/license UNKNOWN)"
        if ($finding) { $findings.Add($finding) }
    }
    return @($findings)
}
