<##
.SYNOPSIS
    唯讀檢查 AetherTune 的本機音訊線路與必要工具。

.DESCRIPTION
    這個檢查器不會修改音訊裝置、啟動錄音、上傳檔案或改寫模型。
    它把「檔案存在」、「Windows 音訊端點存在」、「本機服務可回應」
    和「角色模型已就緒」分開報告，避免把安裝完成誤認為全鏈路完成。
#>

[CmdletBinding()]
param(
    [int]$VcClientPort = 18000,
    [string]$OutFile = '',
    [switch]$RunInferenceProbes,
    [switch]$FailOnWaiting
)

$ErrorActionPreference = 'Continue'
$projectRoot = Split-Path -Parent $PSScriptRoot
$results = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param(
        [string]$Component,
        [ValidateSet('PASS', 'WAITING', 'BLOCKED', 'INFO')]
        [string]$Status,
        [string]$Evidence
    )

    $results.Add([pscustomobject]@{
        Component = $Component
        Status    = $Status
        Evidence  = ($Evidence -replace '\r?\n', ' ').Trim()
    })
}

function Find-FirstFile {
    param([string[]]$Candidates)
    foreach ($candidate in $Candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }
    return $null
}

function Get-Hash {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    return $null
}

function Add-LoopbackArtifactCheck {
    param(
        [string]$Component,
        [string]$WavPath,
        [string]$ReportPath,
        [string]$ExpectedOutputFragment,
        [string]$ExpectedInputFragment
    )

    if (-not (Test-Path -LiteralPath $WavPath -PathType Leaf)) {
        Add-Check $Component 'WAITING' "尚未產生 WAV；請執行 tools/virtual_cable_loopback.py"
        return
    }
    if (-not (Test-Path -LiteralPath $ReportPath -PathType Leaf)) {
        Add-Check $Component 'WAITING' 'WAV 存在但缺少同名 JSON 證據；請重新執行 loopback，不能只以檔案存在判定 PASS'
        return
    }

    try {
        $report = Get-Content -LiteralPath $ReportPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $actualHash = Get-Hash $WavPath
        $reportedHash = [string]$report.wav_sha256
        $hashMatches = $reportedHash -and ($actualHash -eq $reportedHash.ToLowerInvariant())
        $metricsOk = ([double]$report.captured_frames -ge [double]$report.minimum_captured_frames) -and ([double]$report.rms -ge 0.01)
        $routeMatches = ($report.test -eq 'wasapi-synthetic-loopback') -and
            ([string]$report.output_fragment -like "*$ExpectedOutputFragment*") -and
            ([string]$report.input_fragment -like "*$ExpectedInputFragment*")
        $pathMatches = $false
        if ($report.wav_path) {
            try { $pathMatches = ((Resolve-Path -LiteralPath ([string]$report.wav_path)).Path -eq (Resolve-Path -LiteralPath $WavPath).Path) } catch { $pathMatches = $false }
        }
        if (-not $hashMatches -or -not $routeMatches -or -not $pathMatches) {
            Add-Check $Component 'BLOCKED' "loopback JSON、路由、WAV path 或 hash 不一致；expected_output=$ExpectedOutputFragment; expected_input=$ExpectedInputFragment; report=$ReportPath; actual_sha256=$actualHash; reported_sha256=$reportedHash"
        } elseif ($report.status -eq 'PASS' -and $metricsOk) {
            Add-Check $Component 'PASS' "report=$ReportPath; frames=$($report.captured_frames)/$($report.requested_frames); rms=$($report.rms); peak=$($report.peak); sha256=$actualHash"
        } elseif ($report.status -eq 'FAIL') {
            Add-Check $Component 'WAITING' "已實際執行但訊號未通過；frames=$($report.captured_frames)/$($report.requested_frames); rms=$($report.rms); report=$ReportPath"
        } else {
            Add-Check $Component 'BLOCKED' "loopback status 或 metrics 不一致；report=$ReportPath; status=$($report.status); metrics_ok=$metricsOk"
        }
    } catch {
        Add-Check $Component 'BLOCKED' "無法解析 loopback evidence：$($_.Exception.Message)"
    }
}

function Add-VoicemeeterRouteArtifactCheck {
    param(
        [string]$ReportPath,
        [string]$WavPath
    )

    $component = 'Voicemeeter B1 Remote API route diagnosis'
    if (-not (Test-Path -LiteralPath $WavPath -PathType Leaf) -or -not (Test-Path -LiteralPath $ReportPath -PathType Leaf)) {
        Add-Check $component 'WAITING' "尚未產生唯讀 Remote API route report；請執行 tools/voicemeeter-route-check.py"
        return
    }

    try {
        $report = Get-Content -LiteralPath $ReportPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $actualHash = Get-Hash $WavPath
        $reportedHash = [string]$report.wav_sha256
        $hashMatches = $reportedHash -and ($actualHash -eq $reportedHash.ToLowerInvariant())
        $metricsOk = ([double]$report.captured_frames -ge [double]$report.minimum_captured_frames) -and ([double]$report.rms -ge 0.01)
        $pathMatches = $false
        if ($report.wav_path) {
            try { $pathMatches = ((Resolve-Path -LiteralPath ([string]$report.wav_path)).Path -eq (Resolve-Path -LiteralPath $WavPath).Path) } catch { $pathMatches = $false }
        }
        $parameterMap = @{}
        if ($report.parameters) {
            foreach ($property in $report.parameters.PSObject.Properties) {
                $parameterMap[$property.Name] = [double]$property.Value.value
            }
        }
        $routeConfigOk = ($parameterMap['Strip[2].B1'] -eq 1) -and
            ($parameterMap['Strip[2].Mute'] -eq 0) -and
            ($parameterMap['Bus[1].Mute'] -eq 0)
        $levelCount = 0
        if ($report.level_maxima) {
            foreach ($levelType in $report.level_maxima.PSObject.Properties) {
                $levelCount += @($levelType.Value.PSObject.Properties).Count
            }
        }
        $apiOk = (-not $report.api_error) -and (-not $report.stream_error) -and ($levelCount -gt 0)
        if (-not $hashMatches -or -not $pathMatches -or -not $routeConfigOk) {
            Add-Check $component 'BLOCKED' "Remote API report、路由參數、WAV path 或 hash 不一致；report=$ReportPath; route_config=$routeConfigOk; actual_sha256=$actualHash; reported_sha256=$reportedHash"
        } elseif ($report.status -eq 'PASS' -and $metricsOk -and $apiOk) {
            Add-Check $component 'PASS' "report=$ReportPath; frames=$($report.captured_frames)/$($report.requested_frames); rms=$($report.rms); nonzero_api_levels=$levelCount; sha256=$actualHash"
        } else {
            Add-Check $component 'WAITING' "Remote API/endpoint 可檢查但 B1 訊號未形成完整證據；report=$ReportPath; status=$($report.status); metrics_ok=$metricsOk; api_ok=$apiOk"
        }
    } catch {
        Add-Check $component 'BLOCKED' "無法解析 Voicemeeter Remote API evidence：$($_.Exception.Message)"
    }
}

# 1. 專案隔離環境與 RVC 訓練基礎資產。
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$rvcRoot = Join-Path $projectRoot 'tools\external\Retrieval-based-Voice-Conversion-WebUI'
$vcMain = Join-Path $projectRoot 'tools\external\VCClient\2.1.4-alpha\dist\main\main.exe'
$lightHost = Join-Path $projectRoot 'tools\external\LightHostModern\app\Light Host Modern.exe'
$graillonVst3 = 'C:\Program Files\Common Files\VST3\Auburn Sounds Graillon 3.vst3\Contents\x86_64-win\Auburn Sounds Graillon 3.vst3'
$ffmpeg = Find-FirstFile @(
    'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
    'C:\ffmpeg\bin\ffmpeg.exe',
    'C:\Users\User\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe'
)

if (Test-Path -LiteralPath $python -PathType Leaf) {
    Add-Check 'AetherTune Python venv' 'PASS' $python
} else {
    Add-Check 'AetherTune Python venv' 'BLOCKED' "找不到 $python"
}

if (Test-Path -LiteralPath $rvcRoot -PathType Container) {
    $rvcHead = (& git -C $rvcRoot rev-parse --short HEAD 2>$null)
    Add-Check 'RVC 官方 repo' 'PASS' "path=$rvcRoot revision=$rvcHead"
} else {
    Add-Check 'RVC 官方 repo' 'BLOCKED' $rvcRoot
}

$pretrained = @(Get-ChildItem (Join-Path $rvcRoot 'assets\pretrained') -Filter '*.pth' -File -ErrorAction SilentlyContinue)
$pretrainedV2 = @(Get-ChildItem (Join-Path $rvcRoot 'assets\pretrained_v2') -Filter '*.pth' -File -ErrorAction SilentlyContinue)
$muteFiles = @(Get-ChildItem (Join-Path $rvcRoot 'logs\mute') -Recurse -File -ErrorAction SilentlyContinue)
if ($pretrained.Count -eq 12 -and $pretrainedV2.Count -eq 12 -and $muteFiles.Count -gt 0) {
    Add-Check 'RVC training assets' 'PASS' "pretrained=$($pretrained.Count), pretrained_v2=$($pretrainedV2.Count), mute=$($muteFiles.Count)"
} else {
    Add-Check 'RVC training assets' 'WAITING' "pretrained=$($pretrained.Count), pretrained_v2=$($pretrainedV2.Count), mute=$($muteFiles.Count)"
}

$roleWeights = @(Get-ChildItem (Join-Path $projectRoot 'models\weights') -Filter '*.pth' -File -ErrorAction SilentlyContinue)
$roleIndexes = @(Get-ChildItem (Join-Path $projectRoot 'models\indexes') -Filter '*.index' -File -ErrorAction SilentlyContinue)
$modelRegister = Join-Path $projectRoot 'models\model-register.csv'
if ($roleWeights.Count -eq 0 -and $roleIndexes.Count -eq 0) {
    Add-Check '角色模型（.pth/.index）' 'WAITING' '尚無角色模型；需先完成訓練、extraction、交接與 model-register 登記'
} elseif (-not (Test-Path -LiteralPath $modelRegister -PathType Leaf)) {
    Add-Check '角色模型（.pth/.index）' 'WAITING' "模型檔案存在但缺少 $modelRegister；不能只以兩個資料夾有檔案判定配對完成"
} else {
    $modelIssues = [System.Collections.Generic.List[string]]::new()
    try {
        $registeredModels = @(Import-Csv -LiteralPath $modelRegister)
        $registeredWeightPaths = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
        $registeredIndexPaths = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
        $seenModelIds = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
        foreach ($model in $registeredModels) {
            foreach ($field in @('model_id', 'status', 'weights_relative_path', 'index_relative_path', 'weights_sha256', 'index_sha256', 'sample_rate', 'f0', 'version', 'dataset_batch_id', 'rvc_revision', 'source_url', 'license_or_permission', 'training_environment')) {
                if (-not ([string]$model.$field).Trim()) {
                    $modelIssues.Add("$($model.model_id): missing $field")
                }
                elseif ([string]$model.$field -match '(?i)^(unknown|pending|pending-manual|replace_with_)') {
                    $modelIssues.Add("$($model.model_id): $field 仍是未知或 placeholder")
                }
            }
            if (-not $seenModelIds.Add(([string]$model.model_id).Trim())) {
                $modelIssues.Add("$($model.model_id): model_id 重複")
            }
            if ([string]$model.status -notin @('candidate', 'ready', 'retired')) {
                $modelIssues.Add("$($model.model_id): status 必須是 candidate、ready 或 retired")
            }
            $weightPath = Join-Path $projectRoot (($model.weights_relative_path -replace '/', '\'))
            $indexPath = Join-Path $projectRoot (($model.index_relative_path -replace '/', '\'))
            $registeredWeightPaths.Add((([string]$model.weights_relative_path).Replace('\', '/') -replace '^\./', '')) | Out-Null
            $registeredIndexPaths.Add((([string]$model.index_relative_path).Replace('\', '/') -replace '^\./', '')) | Out-Null
            if (-not (Test-Path -LiteralPath $weightPath -PathType Leaf)) { $modelIssues.Add("$($model.model_id): weights 不存在") }
            if (-not (Test-Path -LiteralPath $indexPath -PathType Leaf)) { $modelIssues.Add("$($model.model_id): index 不存在") }
            if ([string]$model.weights_sha256 -notmatch '^[0-9a-fA-F]{64}$') {
                $modelIssues.Add("$($model.model_id): weights_sha256 必須是 64 位十六進位 SHA-256，不能使用 placeholder")
            } elseif (Test-Path -LiteralPath $weightPath -PathType Leaf) {
                if ((Get-Hash $weightPath) -ne ([string]$model.weights_sha256).ToLowerInvariant()) { $modelIssues.Add("$($model.model_id): weights SHA-256 不一致") }
            }
            if ([string]$model.index_sha256 -notmatch '^[0-9a-fA-F]{64}$') {
                $modelIssues.Add("$($model.model_id): index_sha256 必須是 64 位十六進位 SHA-256，不能使用 placeholder")
            } elseif (Test-Path -LiteralPath $indexPath -PathType Leaf) {
                if ((Get-Hash $indexPath) -ne ([string]$model.index_sha256).ToLowerInvariant()) { $modelIssues.Add("$($model.model_id): index SHA-256 不一致") }
            }
        }
        foreach ($weight in $roleWeights) {
            $relative = $weight.FullName.Substring($projectRoot.Length + 1).Replace('\', '/')
            if (-not $registeredWeightPaths.Contains($relative)) { $modelIssues.Add("未登記 weights：$relative") }
        }
        foreach ($index in $roleIndexes) {
            $relative = $index.FullName.Substring($projectRoot.Length + 1).Replace('\', '/')
            if (-not $registeredIndexPaths.Contains($relative)) { $modelIssues.Add("未登記 index：$relative") }
        }
        if ($registeredModels.Count -eq 0) {
            Add-Check '角色模型（.pth/.index）' 'WAITING' "模型檔案存在但 $modelRegister 沒有登記資料"
        } elseif ($modelIssues.Count -gt 0) {
            Add-Check '角色模型（.pth/.index）' 'BLOCKED' ($modelIssues -join '; ')
        } elseif (@($registeredModels | Where-Object { $_.status -eq 'ready' }).Count -gt 0) {
            $readyCount = @($registeredModels | Where-Object { $_.status -eq 'ready' }).Count
            Add-Check '角色模型（.pth/.index）' 'PASS' "ready_models=$readyCount; weights=$($roleWeights.Count), indexes=$($roleIndexes.Count), register=$modelRegister"
        } else {
            Add-Check '角色模型（.pth/.index）' 'WAITING' '模型已登記且 hash 合法，但沒有 status=ready 的可用模型；candidate/retired 不得作為推論輸入'
        }
    } catch {
        Add-Check '角色模型（.pth/.index）' 'BLOCKED' "無法解析 $modelRegister：$($_.Exception.Message)"
    }
}

# 2. 外部工具檔案。
if ($ffmpeg) {
    Add-Check 'FFmpeg/FFprobe' 'PASS' $ffmpeg
} else {
    Add-Check 'FFmpeg/FFprobe' 'BLOCKED' '找不到 ffmpeg.exe'
}

if (Test-Path -LiteralPath $vcMain -PathType Leaf) {
    $vcProcess = @(Get-Process -Name main -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $vcMain })
    Add-Check 'VCClient package' 'PASS' "path=$vcMain process=$($vcProcess.Count)"
} else {
    Add-Check 'VCClient package' 'BLOCKED' $vcMain
}

$vcTorchVersionFile = Join-Path (Split-Path -Parent $vcMain) '_internal\torch\version.py'
$vcLogPath = Join-Path (Split-Path -Parent $vcMain) 'vcclient.log'
if (Test-Path -LiteralPath $vcTorchVersionFile -PathType Leaf) {
    $vcTorchText = Get-Content -LiteralPath $vcTorchVersionFile -Raw
    $vcTorchVersion = [regex]::Match($vcTorchText, "__version__\s*=\s*'([^']+)'").Groups[1].Value
    $projectGpu = if (Test-Path -LiteralPath $python -PathType Leaf) { (& $python -c "import torch; print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no-cuda'); print(torch.cuda.get_device_capability(0) if torch.cuda.is_available() else '')" 2>&1 | Out-String).Trim() } else { 'project venv unavailable' }
    $vcLogEvidence = 'log=missing'
    if (Test-Path -LiteralPath $vcLogPath -PathType Leaf) {
        $vcLogText = Get-Content -LiteralPath $vcLogPath -Raw
        $cudaBuild = [regex]::Match($vcLogText, 'cuda_version\(build\):([^,\r\n]+)').Groups[1].Value.Trim()
        $gpuAvailable = if ($vcLogText -match 'GPU\[cuda\]\(1\): available:True') { 'available=True' } else { 'available=True not found' }
        $vcLogEvidence = "log=$gpuAvailable; cuda_build=$cudaBuild; path=$vcLogPath"
    }
    if ($vcTorchVersion -match '\+cu118' -and $projectGpu -match '12,?\s*0') {
        Add-Check 'VCClient bundled CUDA runtime gate' 'WAITING' "VCClient embedded torch=$vcTorchVersion; detected GPU capability=$projectGpu; $vcLogEvidence; package log must be validated with a real role model because cu118/sm_120 is not proven compatible"
    } else {
        Add-Check 'VCClient bundled CUDA runtime gate' 'WAITING' "VCClient embedded torch=$vcTorchVersion; project GPU=$projectGpu; $vcLogEvidence; UI/GPU discovery is not a real role-model inference proof"
    }
} else {
    Add-Check 'VCClient bundled CUDA runtime gate' 'BLOCKED' "找不到 VCClient embedded torch version: $vcTorchVersionFile"
}

if (Test-Path -LiteralPath $lightHost -PathType Leaf) {
    $hostProcess = @(Get-Process -Name 'Light Host Modern' -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $lightHost })
    Add-Check 'Light Host Modern' 'PASS' "path=$lightHost process=$($hostProcess.Count)"
} else {
    Add-Check 'Light Host Modern' 'BLOCKED' $lightHost
}

if (Test-Path -LiteralPath $graillonVst3 -PathType Leaf) {
    Add-Check 'Graillon VST3 binary' 'PASS' $graillonVst3
    Add-Check 'Graillon loaded in Light Host' 'WAITING' 'VST3 binary 存在，但尚未以 Light Host chain、bypass/active loopback 證明已載入與處理音訊'
} else {
    Add-Check 'Graillon VST3' 'WAITING' '尚未找到已安裝的 Graillon VST3 binary'
}

# 3. Windows 音訊端點。這是唯讀查詢；不會更改預設裝置。
# 端點驗收以 PortAudio 的 input/output channel 能力為主；CIM/DirectShow
# 只能作為名稱線索，不能在沒有方向證據時讓整組端點 PASS。
$dshow = ''
if ($ffmpeg) {
    try { $dshow = (& $ffmpeg -hide_banner -list_devices true -f dshow -i dummy 2>&1 | Out-String) } catch { $dshow = "ffmpeg_error=$($_.Exception.Message)" }
}
$portAudioRaw = ''
$portAudioDevices = @()
if (Test-Path -LiteralPath $python -PathType Leaf) {
    try {
        # 每行一個 JSON object，兼容 Windows PowerShell 5.1 不會正確展開 JSON array 的行為。
        $portAudioRaw = (& $python -c "import sounddevice as sd, json; print('\n'.join(json.dumps({'name': str(item['name']), 'input_channels': int(item['max_input_channels']), 'output_channels': int(item['max_output_channels'])}, ensure_ascii=False) for item in sd.query_devices()))" 2>&1 | Out-String).Trim()
        $portAudioDevices = @($portAudioRaw -split '\r?\n' | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json })
    } catch {
        $portAudioRaw = "portaudio_error=$($_.Exception.Message)"
        $portAudioDevices = @()
    }
}
$audioEndpointEvidence = "$dshow $portAudioRaw"
$cimError = $null
$soundDevices = @(Get-CimInstance Win32_SoundDevice -ErrorAction SilentlyContinue -ErrorVariable cimError)
$inventoryStatus = if ($portAudioDevices.Count -gt 0) { 'PASS' } else { 'BLOCKED' }
if ($portAudioDevices.Count -gt 0) {
    Add-Check 'Windows audio endpoint inventory' $inventoryStatus "PortAudio inventory=$($portAudioDevices.Count); CIM=$($soundDevices.Count); cim_error=$($cimError -join ' ')"
} else {
    Add-Check 'Windows audio endpoint inventory' $inventoryStatus "無法取得含 input/output channel 方向的 PortAudio inventory；CIM=$($soundDevices.Count); $audioEndpointEvidence"
}
$requiredEndpoints = @(
    @{ Component = 'Endpoint: CABLE Input playback'; Fragment = 'CABLE Input'; Direction = 'output_channels' },
    @{ Component = 'Endpoint: CABLE Output recording'; Fragment = 'CABLE Output'; Direction = 'input_channels' },
    @{ Component = 'Endpoint: Voicemeeter Input playback'; Fragment = 'Voicemeeter Input'; Direction = 'output_channels' },
    @{ Component = 'Endpoint: Voicemeeter Out B1 recording'; Fragment = 'Voicemeeter Out B1'; Direction = 'input_channels' },
    @{ Component = 'Endpoint: physical microphone recording'; Fragment = '麥克風|Microphone|HyperX'; Direction = 'input_channels' }
)
foreach ($required in $requiredEndpoints) {
    $match = @($portAudioDevices | Where-Object {
        ([string]$_.name -match $required.Fragment) -and ([int]$_.($required.Direction) -gt 0)
    })
    if ($match.Count -gt 0) {
        Add-Check $required.Component 'PASS' (($match | ForEach-Object { "$($_.name); input=$($_.input_channels); output=$($_.output_channels)" }) -join ' | ')
    } elseif ($portAudioDevices.Count -gt 0) {
        Add-Check $required.Component 'BLOCKED' "找不到具備 $($required.Direction) > 0 的端點；expected=$($required.Fragment)"
    } else {
        Add-Check $required.Component 'BLOCKED' "沒有可驗證方向的 PortAudio inventory；expected=$($required.Fragment) / $($required.Direction)"
    }
}

# 這些 artifact 由 tools/virtual_cable_loopback.py 產生；不會自動錄製實體麥克風。
$cableLoopback = Join-Path $projectRoot 'artifacts\virtual-cable-loopback.wav'
Add-LoopbackArtifactCheck 'VB-CABLE synthetic loopback' $cableLoopback (Join-Path $projectRoot 'artifacts\virtual-cable-loopback.json') 'CABLE Input' 'CABLE Output'
$vmLoopback = Join-Path $projectRoot 'artifacts\voicemeeter-b1-loopback.wav'
Add-LoopbackArtifactCheck 'Voicemeeter B1 synthetic loopback' $vmLoopback (Join-Path $projectRoot 'artifacts\voicemeeter-b1-loopback.json') 'Voicemeeter Input' 'Voicemeeter Out B1'
$vmRouteReport = Join-Path $projectRoot 'artifacts\voicemeeter-b1-route-check.json'
$vmRouteWav = Join-Path $projectRoot 'artifacts\voicemeeter-b1-route-check.wav'
Add-VoicemeeterRouteArtifactCheck $vmRouteReport $vmRouteWav

# 4. VCClient health endpoint。只做 GET，不操作模型與音訊。
try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:$VcClientPort/" -UseBasicParsing -TimeoutSec 3
    if ($health.StatusCode -eq 200) {
        Add-Check 'VCClient localhost Web UI' 'PASS' "http://127.0.0.1:$VcClientPort/ HTTP $($health.StatusCode)"
    } else {
        Add-Check 'VCClient localhost Web UI' 'WAITING' "HTTP $($health.StatusCode)"
    }
} catch {
    Add-Check 'VCClient localhost Web UI' 'WAITING' "尚未啟動或 port $VcClientPort 無法連線"
}

# 5. 專案 venv 的 CUDA smoke probe；另以固定 sample ONNX 實際跑一次 inference。
if (Test-Path -LiteralPath $python -PathType Leaf) {
    # 避免 Windows PowerShell 5.1 對 native command 內嵌引號的重組；這段故意不含
    # Python 字串 literal，仍會執行 CUDA tensor multiply 與同步。
    $probeCode = 'import torch, onnxruntime; x=torch.ones((64,64), device=torch.device(0)); y=x @ x; torch.cuda.synchronize(); print(torch.__version__); print(torch.cuda.is_available()); print(float(y[0,0])); print(onnxruntime.get_available_providers())'
    $probe = (& $python -c $probeCode 2>&1)
    if ($LASTEXITCODE -eq 0 -and ($probe -join ' ') -match '\bTrue\b' -and ($probe -join ' ') -match '\b64(\.0+)?\b') {
        Add-Check 'RVC venv CUDA runtime' 'PASS' ($probe -join ' ')
    } else {
        Add-Check 'RVC venv CUDA runtime' 'BLOCKED' ($probe -join ' ')
    }

    # VCClient 2.1.4-alpha stores the downloaded official sample under
    # upload_dir; older packaged layouts used model_dir\0. Accept both
    # layouts, but always hash and record the actual selected file.
    $sampleOnnxCandidates = @(
        (Join-Path $projectRoot 'tools\external\VCClient\2.1.4-alpha\dist\main\model_dir\0\kikoto_kurage_v2_40k_e100.onnx'),
        (Join-Path $projectRoot 'tools\external\VCClient\2.1.4-alpha\dist\main\upload_dir\kikoto_kurage_v2_40k_e100.onnx')
    )
    $sampleOnnx = $sampleOnnxCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace([string]$sampleOnnx)) {
        $sampleOnnx = $sampleOnnxCandidates[0]
    }
    $onnxReport = Join-Path $projectRoot 'artifacts\onnx-runtime-probe.json'
    $probeRunId = [guid]::NewGuid().ToString()
    if ($RunInferenceProbes -and (Test-Path -LiteralPath $sampleOnnx -PathType Leaf)) {
        $probeOutput = (& $python (Join-Path $projectRoot 'tools\onnx_runtime_probe.py') --model $sampleOnnx --artifact $onnxReport --run-id $probeRunId 2>&1)
        $probeExit = $LASTEXITCODE
    } elseif ($RunInferenceProbes) {
        $probeOutput = "找不到 sample ONNX：$sampleOnnx"
        $probeExit = 2
    } else {
        $probeOutput = ''
        $probeExit = $null
    }
    if (-not $RunInferenceProbes) {
        Add-Check 'Project ONNX synthetic inference' 'WAITING' '本次未執行 probe；已忽略舊 artifact，需加上 -RunInferenceProbes 才能建立當次證據'
    } elseif ($probeExit -ne 0) {
        Add-Check 'Project ONNX synthetic inference' 'BLOCKED' "本次 probe exit=$probeExit；未採用舊 artifact。output=$($probeOutput -join ' ')"
    } elseif (-not (Test-Path -LiteralPath $onnxReport -PathType Leaf)) {
        Add-Check 'Project ONNX synthetic inference' 'BLOCKED' "本次 probe 成功回傳但找不到 artifact=$onnxReport"
    } else {
        try {
            $onnxEvidence = Get-Content -LiteralPath $onnxReport -Raw -Encoding UTF8 | ConvertFrom-Json
            $expectedModelHash = Get-Hash $sampleOnnx
            $reportStartedAt = [DateTimeOffset]::Parse([string]$onnxEvidence.started_at_utc)
            $timestampValid = $reportStartedAt -gt [DateTimeOffset]::MinValue
            $freshEvidence = ([string]$onnxEvidence.run_id -eq $probeRunId) -and
                ([string]$onnxEvidence.model_sha256 -eq $expectedModelHash) -and
                $timestampValid
            if (-not $freshEvidence) {
                Add-Check 'Project ONNX synthetic inference' 'BLOCKED' "artifact 不是本次 probe 證據；run_id/model hash/timestamp 不符。expected_run_id=$probeRunId; artifact=$onnxReport"
            } elseif ($onnxEvidence.status -eq 'ok') {
                $executed = ($onnxEvidence.executed_providers -join ', ')
                if ($executed -match 'CUDAExecutionProvider') {
                    Add-Check 'Project ONNX synthetic inference' 'PASS' "run_id=$($onnxEvidence.run_id); model_sha256=$($onnxEvidence.model_sha256); executed=$executed; output_shape=$($onnxEvidence.output_shape -join 'x'); artifact=$onnxReport"
                } else {
                    Add-Check 'Project ONNX synthetic inference' 'WAITING' "run_id=$($onnxEvidence.run_id); model_sha256=$($onnxEvidence.model_sha256); inference 成功但實際 provider=$executed（目前不是 CUDA）；requested=$($onnxEvidence.requested_provider); artifact=$onnxReport"
                }
            } else {
                Add-Check 'Project ONNX synthetic inference' 'BLOCKED' "probe status=$($onnxEvidence.status); error=$($onnxEvidence.error); artifact=$onnxReport"
            }
        } catch {
            Add-Check 'Project ONNX synthetic inference' 'BLOCKED' "無法解析 $onnxReport：$($_.Exception.Message)"
        }
    }
}

$table = ($results | Select-Object Component,Status,Evidence | ConvertTo-Csv -NoTypeInformation | Out-String).Trim()
$passCount = @($results | Where-Object Status -eq 'PASS').Count
$waitingCount = @($results | Where-Object Status -eq 'WAITING').Count
$blockedCount = @($results | Where-Object Status -eq 'BLOCKED').Count
$timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'

Write-Output "AetherTune wiring verification - $timestamp"
Write-Output "PASS=$passCount WAITING=$waitingCount BLOCKED=$blockedCount"
$results | Format-Table -AutoSize

if ($OutFile) {
    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add('# AetherTune Wiring Verification')
    $lines.Add('')
    $lines.Add("檢查時間：$timestamp")
    $lines.Add('')
    $lines.Add("摘要：PASS=$passCount；WAITING=$waitingCount；BLOCKED=$blockedCount")
    $lines.Add("")
    $lines.Add("RunInferenceProbes：$RunInferenceProbes；FailOnWaiting：$FailOnWaiting")
    $lines.Add('')
    $lines.Add('| 元件 | 狀態 | 證據 |')
    $lines.Add('|---|---|---|')
    foreach ($row in $results) {
        $evidence = $row.Evidence.Replace('|', '\|')
        $lines.Add("| $($row.Component) | $($row.Status) | $evidence |")
    }
    $lines.Add('')
    $lines.Add('這是唯讀驗證；沒有錄製實體麥克風、沒有改寫預設音訊裝置。合成 loopback 與 ONNX probe 只會寫入 artifacts/ 證據，不代表角色音色品質或 Discord/OBS 已驗收。')
    Set-Content -LiteralPath $OutFile -Value $lines -Encoding UTF8
    Write-Output "Report=$OutFile"
}

if ($blockedCount -gt 0) {
    exit 2
}
if ($FailOnWaiting -and $waitingCount -gt 0) {
    exit 3
}
