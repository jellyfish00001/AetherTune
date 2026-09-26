#Requires -Version 7.0

function Resolve-SeedVcEndpoint {
    param(
        [Parameter(Mandatory)][object[]]$DeviceRows,
        [string]$RequestedName,
        [Parameter(Mandatory)][ValidateSet('input', 'output')][string]$Direction,
        [int]$DefaultIndex = -1,
        [string]$HostApiFilter
    )

    $channelField = if ($Direction -eq 'input') { 'max_input_channels' } else { 'max_output_channels' }
    $matches = @($DeviceRows | Where-Object {
        $_.$channelField -gt 0 -and
        ((-not $RequestedName) -or ([string]$_.name -ceq $RequestedName)) -and
        ((-not $HostApiFilter) -or ([string]$_.hostapi_name -ceq $HostApiFilter))
    })
    if ($RequestedName) {
        if ($matches.Count -ne 1) {
            throw "Device name '$RequestedName' resolves to $($matches.Count) $Direction endpoints under Host API '$HostApiFilter'; use an exact unique name and -HostApi if needed."
        }
    }
    else {
        $matches = @($matches | Where-Object { [int]$_.index -eq $DefaultIndex })
        if ($matches.Count -ne 1) {
            throw "No unique default $Direction endpoint is available under Host API '$HostApiFilter'. Pass -${Direction}DeviceName and, when needed, -HostApi."
        }
    }
    return $matches[0]
}

function Resolve-SeedVcDevicePair {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object[]]$DeviceRows,
        [Parameter(Mandatory)][string[]]$HostApiNames,
        [int]$DefaultInputIndex = -1,
        [int]$DefaultOutputIndex = -1,
        [string]$InputDeviceName,
        [string]$SavedInputDeviceName,
        [string]$OutputDeviceName,
        [string]$SavedOutputDeviceName,
        [string]$RequestedHostApi,
        [string]$SavedHostApi
    )

    # Normalize the runtime inventory once so preflight and startup share identical matching.
    $normalizedRows = @(
        foreach ($row in $DeviceRows) {
            $apiName = $null
            $namedApi = $row.PSObject.Properties['hostapi_name']
            if ($namedApi -and $namedApi.Value) {
                $apiName = [string]$namedApi.Value
            }
            else {
                $apiIndexProperty = $row.PSObject.Properties['hostapi']
                if (-not $apiIndexProperty) { throw 'PortAudio device row is missing Host API identity.' }
                $apiIndex = [int]$apiIndexProperty.Value
                if ($apiIndex -lt 0 -or $apiIndex -ge $HostApiNames.Count) { throw "PortAudio device row has invalid Host API index: $apiIndex" }
                $apiName = [string]$HostApiNames[$apiIndex]
            }
            [pscustomobject]@{
                index = [int]$row.index
                name = [string]$row.name
                hostapi_name = $apiName
                max_input_channels = [int]$row.max_input_channels
                max_output_channels = [int]$row.max_output_channels
            }
        }
    )

    # An explicit CLI Host API overrides persisted settings; otherwise keep the saved API.
    $hostApiFilter = if ($RequestedHostApi) { $RequestedHostApi } elseif ($SavedHostApi) { $SavedHostApi } else { $null }
    $inputRequest = if ($InputDeviceName) { $InputDeviceName } else { $SavedInputDeviceName }
    $outputRequest = if ($OutputDeviceName) { $OutputDeviceName } else { $SavedOutputDeviceName }
    $savedApiIsAuthoritative = (-not $RequestedHostApi) -and [bool]$SavedHostApi

    try {
        $inputDevice = Resolve-SeedVcEndpoint -DeviceRows $normalizedRows -RequestedName $inputRequest -Direction input -DefaultIndex $DefaultInputIndex -HostApiFilter $hostApiFilter
        $effectiveHostApi = if ($hostApiFilter) { $hostApiFilter } else { $inputDevice.hostapi_name }
        $outputDevice = Resolve-SeedVcEndpoint -DeviceRows $normalizedRows -RequestedName $outputRequest -Direction output -DefaultIndex $DefaultOutputIndex -HostApiFilter $effectiveHostApi
        if ($inputDevice.hostapi_name -cne $outputDevice.hostapi_name) {
            throw "Input and output endpoints use different Host APIs: $($inputDevice.hostapi_name) / $($outputDevice.hostapi_name)."
        }
    }
    catch {
        if ($savedApiIsAuthoritative) {
            throw "Saved Host API '$SavedHostApi' could not resolve the requested device pair. Pass -HostApi <available Host API> to override the saved selection. $($_.Exception.Message)"
        }
        throw
    }

    return [pscustomobject]@{
        Input = $inputDevice
        Output = $outputDevice
        HostApi = [string]$effectiveHostApi
    }
}
