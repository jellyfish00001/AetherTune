function Test-VcClientChunkResponse {
    [CmdletBinding()]
    param(
        [AllowNull()][byte[]]$ResponseBytes
    )

    $length = if ($null -eq $ResponseBytes) { 0 } else { $ResponseBytes.Length }
    $result = [ordered]@{
        valid = $false
        reason = $null
        output_bytes = $length
        sample_count = 0
        finite_samples = 0
        nonfinite_samples = 0
        nonzero_samples = 0
        output_all_zero = $false
    }

    if ($length -eq 0) {
        $result.reason = 'empty'
        return [pscustomobject]$result
    }
    if ($length -lt 4) {
        $result.reason = 'short'
        return [pscustomobject]$result
    }
    if (($length % 4) -ne 0) {
        $result.reason = 'unaligned'
        return [pscustomobject]$result
    }

    $samples = [float[]]::new([int]($length / 4))
    [Buffer]::BlockCopy($ResponseBytes, 0, $samples, 0, $length)
    $result.sample_count = $samples.Length
    foreach ($sample in $samples) {
        if ([float]::IsFinite($sample)) {
            $result.finite_samples++
            if ([Math]::Abs([double]$sample) -gt 0) {
                $result.nonzero_samples++
            }
        } else {
            $result.nonfinite_samples++
        }
    }

    if ($result.nonfinite_samples -gt 0) {
        $result.reason = 'nonfinite'
        return [pscustomobject]$result
    }
    if ($result.nonzero_samples -eq 0) {
        $result.output_all_zero = $true
        $result.reason = 'all_zero'
        return [pscustomobject]$result
    }

    $result.valid = $true
    $result.reason = 'finite_nonzero'
    return [pscustomobject]$result
}
