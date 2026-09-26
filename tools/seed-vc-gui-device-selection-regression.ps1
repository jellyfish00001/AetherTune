#Requires -Version 7.0
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'seed-vc-gui-device-selection.ps1')

# Runtime is simulated with an isolated, retained fixture; this script never opens GUI or audio devices.
$fixtureRoot = Join-Path $env:TEMP ("aethertune-seed-vc-device-selection-" + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Force -Path $fixtureRoot
$settingsPath = Join-Path $fixtureRoot 'config.json'
$hostApis = @('MME', 'Windows DirectSound', 'Windows WASAPI', 'Windows WDM-KS')
$devices = [System.Collections.Generic.List[object]]::new()
$index = 0
for ($apiIndex = 0; $apiIndex -lt $hostApis.Count; $apiIndex++) {
    $devices.Add([pscustomobject]@{ index = $index++; name = 'Shared Microphone'; hostapi = $apiIndex; max_input_channels = 1; max_output_channels = 0 })
    $devices.Add([pscustomobject]@{ index = $index++; name = 'Shared Output'; hostapi = $apiIndex; max_input_channels = 0; max_output_channels = 2 })
}
$devices.Add([pscustomobject]@{ index = 8; name = 'Default Microphone'; hostapi = 3; max_input_channels = 1; max_output_channels = 0 })
$devices.Add([pscustomobject]@{ index = 9; name = 'Default Output'; hostapi = 3; max_input_channels = 0; max_output_channels = 2 })
$devices.Add([pscustomobject]@{ index = 10; name = 'Unique Microphone'; hostapi = 2; max_input_channels = 1; max_output_channels = 0 })
$devices.Add([pscustomobject]@{ index = 11; name = 'Unique Output'; hostapi = 2; max_input_channels = 0; max_output_channels = 2 })

$duplicateInputs = @($devices | Where-Object { $_.name -ceq 'Shared Microphone' -and $_.max_input_channels -gt 0 })
if ($duplicateInputs.Count -ne 4) { throw "Expected the same input name under four Host APIs; got $($duplicateInputs.Count)." }

$first = Resolve-SeedVcDevicePair `
    -DeviceRows $devices.ToArray() -HostApiNames $hostApis `
    -InputDeviceName 'Shared Microphone' -OutputDeviceName 'Shared Output' `
    -RequestedHostApi 'MME'
if ($first.HostApi -cne 'MME') { throw "First selection did not use CLI override: $($first.HostApi)" }
@{
    sg_input_device = $first.Input.name
    sg_output_device = $first.Output.name
    sg_hostapi = $first.HostApi
} | ConvertTo-Json | Set-Content -LiteralPath $settingsPath -Encoding UTF8

$saved = Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
$second = Resolve-SeedVcDevicePair `
    -DeviceRows $devices.ToArray() -HostApiNames $hostApis `
    -SavedInputDeviceName $saved.sg_input_device -SavedOutputDeviceName $saved.sg_output_device `
    -SavedHostApi $saved.sg_hostapi
if ($second.HostApi -cne 'MME' -or $second.Input.hostapi_name -cne 'MME') {
    throw "Saved Host API was not retained when CLI override was omitted: $($second.HostApi)"
}

$override = Resolve-SeedVcDevicePair `
    -DeviceRows $devices.ToArray() -HostApiNames $hostApis `
    -SavedInputDeviceName $saved.sg_input_device -SavedOutputDeviceName $saved.sg_output_device `
    -RequestedHostApi 'Windows DirectSound' -SavedHostApi $saved.sg_hostapi
if ($override.HostApi -cne 'Windows DirectSound' -or $override.Output.hostapi_name -cne 'Windows DirectSound') {
    throw "Explicit CLI Host API did not override the saved selection: $($override.HostApi)"
}

$staleSavedBlocked = $false
try {
    $null = Resolve-SeedVcDevicePair `
        -DeviceRows $devices.ToArray() -HostApiNames $hostApis `
        -SavedInputDeviceName $saved.sg_input_device -SavedOutputDeviceName $saved.sg_output_device `
        -SavedHostApi 'Removed Host API'
}
catch {
    $staleSavedBlocked = $_.Exception.Message -match '(?i)blocked|could not resolve' -and $_.Exception.Message -match '-HostApi'
}
if (-not $staleSavedBlocked) { throw 'Missing saved Host API was not BLOCKED with a -HostApi override instruction.' }

$uniqueInference = Resolve-SeedVcDevicePair `
    -DeviceRows $devices.ToArray() -HostApiNames $hostApis `
    -InputDeviceName 'Unique Microphone' -OutputDeviceName 'Unique Output'
if ($uniqueInference.HostApi -cne 'Windows WASAPI') { throw "Unique endpoint inference selected the wrong Host API: $($uniqueInference.HostApi)" }

$defaultInference = Resolve-SeedVcDevicePair `
    -DeviceRows $devices.ToArray() -HostApiNames $hostApis `
    -DefaultInputIndex 8 -DefaultOutputIndex 9
if ($defaultInference.HostApi -cne 'Windows WDM-KS') { throw "Default endpoint inference selected the wrong Host API: $($defaultInference.HostApi)" }

Write-Output "PASS Seed-VC device selection regression: duplicate input names span four Host APIs; saved MME retained; CLI DirectSound override honored; stale saved API BLOCKED with override guidance; unique/default inference verified; no GUI/audio stream; fixture=$fixtureRoot"
