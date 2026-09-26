function Get-SeedVcCanonicalDirectoryPath {
    param([Parameter(Mandatory = $true)] [string]$Path)

    return [IO.Path]::GetFullPath($Path).TrimEnd([char[]]@('\', '/'))
}

function Ensure-SeedVcCacheJunction {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)] [string]$LinkPath,
        [Parameter(Mandatory = $true)] [string]$TargetPath
    )

    $link = [IO.Path]::GetFullPath($LinkPath)
    $target = Get-SeedVcCanonicalDirectoryPath -Path $TargetPath
    if (-not (Test-Path -LiteralPath $target -PathType Container)) {
        throw "Seed-VC cache target directory is missing: $target"
    }

    if (-not (Test-Path -LiteralPath $link)) {
        New-Item -ItemType Junction -Path $link -Target $target | Out-Null
        $created = $true
    }
    else {
        $created = $false
    }

    $entry = Get-Item -LiteralPath $link -Force
    if ($entry.LinkType -cne 'Junction') {
        throw "Seed-VC overlay path exists but is not a directory junction; it was preserved: $link"
    }
    $declaredTargets = @($entry.Target)
    if ($declaredTargets.Count -ne 1 -or -not $declaredTargets[0]) {
        throw "Seed-VC overlay junction has no single verifiable target; it was preserved: $link"
    }

    $declaredTarget = Get-SeedVcCanonicalDirectoryPath -Path ([string]$declaredTargets[0])
    $resolvedLink = [System.IO.DirectoryInfo]::new($link).ResolveLinkTarget($true)
    if ($null -eq $resolvedLink) {
        throw "Seed-VC overlay junction could not be resolved; it was preserved: $link"
    }
    $resolvedTarget = Get-SeedVcCanonicalDirectoryPath -Path $resolvedLink.FullName
    if ($declaredTarget -ine $target -or $resolvedTarget -ine $target) {
        throw "Seed-VC overlay junction target mismatch; it was preserved: $link -> $resolvedTarget (expected $target)"
    }

    if ($created) { return 'CREATED_AND_VERIFIED' }
    return 'EXISTING_AND_VERIFIED'
}
