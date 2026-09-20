[CmdletBinding()]
param(
    [switch]$Download,
    [switch]$IncludeSampleModels,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

# 此腳本只處理 VCClient 官方 runtime 資產；不會修改 Git 內的程式碼或模型登錄。
$MainDir = Join-Path $PSScriptRoot 'external\VCClient\2.1.4-alpha\dist\main'
$Items = @(
    [pscustomobject]@{ Id = 'hubert_base.pt'; Url = 'https://huggingface.co/wok000/vcclient_modules/resolve/main/contentvec/hubert_base.pt'; RelativePath = 'modules\contentvec\hubert_base.pt'; Sha256 = 'f54b40fd2802423a5643779c4861af1e9ee9c1564dc9d32f54f20b5ffba7db96'; RequiredFor = 'RVC hubert_base_l12' }
    [pscustomobject]@{ Id = 'contentvec-f.onnx'; Url = 'https://huggingface.co/wok000/vcclient_modules/resolve/main/contentvec/contentvec-f.onnx'; RelativePath = 'modules\contentvec\contentvec-f.onnx'; Sha256 = '4b31ed3d95a568fab7952de923ff7f7d3d17128ea6fce69f665509d24c3156db'; RequiredFor = 'VCClient RVC module set' }
    [pscustomobject]@{ Id = 'rinna_hubert_base-f.onnx'; Url = 'https://huggingface.co/wok000/vcclient_modules/resolve/main/rinna_hubert/rinna_hubert_base-f.onnx'; RelativePath = 'modules\rinna_hubert\rinna_hubert_base-f.onnx'; Sha256 = 'd00e262757fa1550faac53fa6140dad16ca75603a36ecfead468920a9f744a16'; RequiredFor = 'VCClient RVC module set' }
    [pscustomobject]@{ Id = 'onnxcrepe_tiny.onnx'; Url = 'https://huggingface.co/wok000/vcclient_modules/resolve/main/onnxcrepe/tiny.onnx'; RelativePath = 'modules\onnxcrepe\tiny.onnx'; Sha256 = '91fc2a0fd10f965dbf7775995daf50e99273caedd7efd00001f23be649da1bc3'; RequiredFor = 'VCClient pitch module set' }
    [pscustomobject]@{ Id = 'onnxcrepe_full.onnx'; Url = 'https://huggingface.co/wok000/vcclient_modules/resolve/main/onnxcrepe/full.onnx'; RelativePath = 'modules\onnxcrepe\full.onnx'; Sha256 = '119845c72c702e052e5262430f9d120bce46176689aa226c39d09dea5cc3a610'; RequiredFor = 'VCClient pitch module set' }
    [pscustomobject]@{ Id = 'rmvpe_20231006.pt'; Url = 'https://huggingface.co/wok000/vcclient_modules/resolve/main/rmvpe/rmvpe_20231006.pt'; RelativePath = 'modules\rmvpe\rmvpe_20231006.pt'; Sha256 = '6d62215f4306e3ca278246188607209f09af3dc77ed4232efdd069798c4ec193'; RequiredFor = 'VCClient pitch module set' }
    [pscustomobject]@{ Id = 'rmvpe_20231006.onnx'; Url = 'https://huggingface.co/wok000/vcclient_modules/resolve/main/rmvpe/rmvpe_20231006.onnx'; RelativePath = 'modules\rmvpe\rmvpe_20231006.onnx'; Sha256 = '84f0586308e36157f75b77c8591bf636d6719c0c4ba95f8faf3df479e7566219'; RequiredFor = 'RVC RMVPE fallback' }
    [pscustomobject]@{ Id = 'applio_japanese_hubert_base.pt'; Url = 'https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/japanese_hubert_base.pt'; RelativePath = 'modules\applio\applio_japanese_hubert_base.pt'; Sha256 = 'dade3cf824ae0d214f7de8b73e70bae7c101e81f12d93577c4760bf516db4063'; RequiredFor = 'VCClient module set' }
    [pscustomobject]@{ Id = 'applio_chinese_hubert_base.pt'; Url = 'https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/chinese_hubert_base.pt'; RelativePath = 'modules\applio\applio_chinese_hubert_base.pt'; Sha256 = '8cd5db6302ae2e79b5972cd02ae375a42a76170374d6e1952fa78d1fe4e4f756'; RequiredFor = 'VCClient module set' }
    [pscustomobject]@{ Id = 'applio_korean_hubert_base.pt'; Url = 'https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/korean_hubert_base.pt'; RelativePath = 'modules\applio\applio_korean_hubert_base.pt'; Sha256 = '6b42c8453b96b203198c1c280a8821158ea3fa8dbbc2a6220cad1c1489c3e65e'; RequiredFor = 'VCClient module set' }
)

if ($IncludeSampleModels) {
    $Items += @(
        [pscustomobject]@{ Id = 'kikoto_kurage_v2_40k_e100.onnx'; Url = 'https://huggingface.co/wok000/vcclient_model/resolve/main/v2.1/sample/kikoto_kurage/kikoto_kurage_v2_40k_e100.onnx'; RelativePath = 'upload_dir\kikoto_kurage_v2_40k_e100.onnx'; Sha256 = $null; RequiredFor = 'VCClient official female sample' }
        [pscustomobject]@{ Id = 'kikoto_kurage.png'; Url = 'https://huggingface.co/wok000/vcclient_model/resolve/main/v2.1/sample/kikoto_kurage/kikoto_kurage.png'; RelativePath = 'upload_dir\kikoto_kurage.png'; Sha256 = $null; RequiredFor = 'VCClient official female sample icon' }
        [pscustomobject]@{ Id = 'tokina_shigure_v2_40k_e100.onnx'; Url = 'https://huggingface.co/wok000/vcclient_model/resolve/main/v2.1/sample/tokina_shigure/tokina_shigure_v2_40k_e100.onnx'; RelativePath = 'upload_dir\tokina_shigure_v2_40k_e100.onnx'; Sha256 = $null; RequiredFor = 'VCClient official sample' }
        [pscustomobject]@{ Id = 'tokina_shigure.png'; Url = 'https://huggingface.co/wok000/vcclient_model/resolve/main/v2.1/sample/tokina_shigure/tokina_shigure.png'; RelativePath = 'upload_dir\tokina_shigure.png'; Sha256 = $null; RequiredFor = 'VCClient official sample icon' }
        [pscustomobject]@{ Id = 'kikoto_mahiro_v2_40k.onnx'; Url = 'https://huggingface.co/wok000/vcclient_model/resolve/main/v2.1/sample/kikoto_mahiro/kikoto_mahiro_v2_40k.onnx'; RelativePath = 'upload_dir\kikoto_mahiro_v2_40k.onnx'; Sha256 = $null; RequiredFor = 'VCClient official sample' }
        [pscustomobject]@{ Id = 'kikoto_mahiro.png'; Url = 'https://huggingface.co/wok000/vcclient_model/resolve/main/v2.1/sample/kikoto_mahiro/kikoto_mahiro.png'; RelativePath = 'upload_dir\kikoto_mahiro.png'; Sha256 = $null; RequiredFor = 'VCClient official sample icon' }
        [pscustomobject]@{ Id = 'amitaro_73e_2628s_best_epoch.onnx'; Url = 'https://huggingface.co/wok000/vcclient_model/resolve/main/v2.1/sample/amitaro/amitaro_73e_2628s_best_epoch.onnx'; RelativePath = 'upload_dir\amitaro_73e_2628s_best_epoch.onnx'; Sha256 = $null; RequiredFor = 'VCClient official sample' }
        [pscustomobject]@{ Id = 'amitaro.png'; Url = 'https://huggingface.co/wok000/vcclient_model/resolve/main/v2.1/sample/amitaro/amitaro.png'; RelativePath = 'upload_dir\amitaro.png'; Sha256 = $null; RequiredFor = 'VCClient official sample icon' }
        [pscustomobject]@{ Id = 'tsukuyomi_20e_1780s_best_epoch.onnx'; Url = 'https://huggingface.co/wok000/vcclient_model/resolve/main/v2.1/sample/tsukuyomi/tsukuyomi_20e_1780s_best_epoch.onnx'; RelativePath = 'upload_dir\tsukuyomi_20e_1780s_best_epoch.onnx'; Sha256 = $null; RequiredFor = 'VCClient official sample' }
        [pscustomobject]@{ Id = 'tsukuyomi-chan.png'; Url = 'https://huggingface.co/wok000/vcclient_model/resolve/main/v2.1/sample/tsukuyomi/tsukuyomi-chan.png'; RelativePath = 'upload_dir\tsukuyomi-chan.png'; Sha256 = $null; RequiredFor = 'VCClient official sample icon' }
    )
}

function Get-ItemStatus {
    param([pscustomobject]$Item)
    $path = Join-Path $MainDir $Item.RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return [pscustomobject]@{ Id = $Item.Id; Path = $path; Status = 'MISSING'; Sha256 = $null; Bytes = 0; RequiredFor = $Item.RequiredFor }
    }

    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    $valid = [string]::IsNullOrWhiteSpace($Item.Sha256) -or $hash -eq $Item.Sha256
    return [pscustomobject]@{ Id = $Item.Id; Path = $path; Status = $(if ($valid) { 'PASS' } else { 'HASH_MISMATCH' }); Sha256 = $hash; Bytes = (Get-Item -LiteralPath $path).Length; RequiredFor = $Item.RequiredFor }
}

if ($Download) {
    foreach ($item in $Items) {
        $target = Join-Path $MainDir $item.RelativePath
        $targetDir = Split-Path -Parent $target
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

        $existing = Get-ItemStatus -Item $item
        if ($existing.Status -eq 'PASS' -and -not $Force) {
            Write-Host "SKIP $($item.Id) already verified"
            continue
        }

        $partial = "$target.partial"
        if (Test-Path -LiteralPath $partial) {
            Remove-Item -LiteralPath $partial -Force
        }
        Write-Host "DOWNLOAD $($item.Id) -> $target"
        Invoke-WebRequest -Uri $item.Url -OutFile $partial -UseBasicParsing
        Move-Item -LiteralPath $partial -Destination $target -Force
    }
}

$results = foreach ($item in $Items) { Get-ItemStatus -Item $item }
$results | Format-Table -AutoSize

$failed = @($results | Where-Object { $_.Status -ne 'PASS' })
if ($failed.Count -gt 0) {
    Write-Error ("VCClient runtime verification failed: " + (($failed | ForEach-Object { "$($_.Id)=$($_.Status)" }) -join ', '))
    exit 2
}

Write-Host "VCClient runtime verification PASS ($($results.Count) files)."
