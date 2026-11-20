#Requires -Version 5.1
<#
.SYNOPSIS
  winmm（MME）虛擬音訊線 loopback 探測：列舉裝置、播 1 kHz 短脈衝並錄音，回報 peak／RMS／粗 onset。

.DESCRIPTION
  僅用 stdlib PowerShell + Add-Type C# P/Invoke winmm，無外部依賴；相容 pwsh 7 與 Windows PowerShell 5.1。
  Windows MME 裝置名稱會截斷為 31 字元，請以 -Out/-In 名稱片段比對，勿假定完整字串。
  回報的 onset 為 MME buffer 層級粗估，不是 E2E 延遲量測；PASS 條件為 peak > 0.01（正規化浮點）。

.PARAMETER List
  僅列出 waveOut/waveIn 裝置後結束（不播放）。

.PARAMETER Crosstalk
  同時在 -CrosstalkOut/-CrosstalkIn 線上錄音，確認未收到主線訊號（peak 應接近 0）。
#>
[CmdletBinding(DefaultParameterSetName = 'Probe')]
param(
    [switch]$List,
    [Parameter(ParameterSetName = 'Probe')]
    [string]$Out = '',
    [Parameter(ParameterSetName = 'Probe')]
    [string]$In = '',
    [Parameter(ParameterSetName = 'Probe')]
    [string]$Label = 'primary',
    [Parameter(ParameterSetName = 'Probe')]
    [switch]$Crosstalk,
    [Parameter(ParameterSetName = 'Probe')]
    [string]$CrosstalkOut = '',
    [Parameter(ParameterSetName = 'Probe')]
    [string]$CrosstalkIn = '',
    [Parameter(ParameterSetName = 'Probe')]
    [string]$OutJson = '',
    [int]$SampleRate = 48000,
    [double]$ToneMs = 300,
    [double]$CaptureSec = 2,
    [double]$ToneLevel = 6000.0 / 32768.0,
    [double]$OnsetThreshold = 0.05,
    [double]$PassPeakMin = 0.01,
    [int]$TimeoutMs = 15000
)

$ErrorActionPreference = 'Stop'

if (-not ([System.Management.Automation.PSTypeName]'AetherTuneVirtualLineProbe').Type) {
    $csharp = @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

public static class AetherTuneVirtualLineProbe
{
    private const int WAVE_FORMAT_PCM = 1;
    private const int CALLBACK_NULL = 0;
    private const int WHDR_DONE = 1;
    private const int WHDR_PREPARED = 2;

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
    public struct WAVEOUTCAPS
    {
        public ushort wMid;
        public ushort wPid;
        public uint vDriverVersion;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
        public string szPname;
        public uint dwFormats;
        public ushort wChannels;
        public ushort wReserved1;
        public uint dwSupport;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
    public struct WAVEINCAPS
    {
        public ushort wMid;
        public ushort wPid;
        public uint vDriverVersion;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
        public string szPname;
        public uint dwFormats;
        public ushort wChannels;
        public ushort wReserved1;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct WAVEFORMATEX
    {
        public ushort wFormatTag;
        public ushort nChannels;
        public uint nSamplesPerSec;
        public uint nAvgBytesPerSec;
        public ushort nBlockAlign;
        public ushort wBitsPerSample;
        public ushort cbSize;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct WAVEHDR
    {
        public IntPtr lpData;
        public uint dwBufferLength;
        public uint dwBytesRecorded;
        public IntPtr dwUser;
        public uint dwFlags;
        public uint dwLoops;
        public IntPtr lpNext;
        public IntPtr reserved;
    }

    [DllImport("winmm.dll", CharSet = CharSet.Auto)]
    private static extern int waveOutGetNumDevs();

    [DllImport("winmm.dll", CharSet = CharSet.Auto)]
    private static extern int waveOutGetDevCaps(int uDeviceID, ref WAVEOUTCAPS pwoc, int cbwoc);

    [DllImport("winmm.dll", CharSet = CharSet.Auto)]
    private static extern int waveInGetNumDevs();

    [DllImport("winmm.dll", CharSet = CharSet.Auto)]
    private static extern int waveInGetDevCaps(int uDeviceID, ref WAVEINCAPS pwic, int cbwic);

    [DllImport("winmm.dll")]
    private static extern int waveOutOpen(out IntPtr phwo, int uDeviceID, ref WAVEFORMATEX pwfx, IntPtr dwCallback, IntPtr dwInstance, int fdwOpen);

    [DllImport("winmm.dll")]
    private static extern int waveOutPrepareHeader(IntPtr hwo, ref WAVEHDR pwh, int cbwh);

    [DllImport("winmm.dll")]
    private static extern int waveOutWrite(IntPtr hwo, ref WAVEHDR pwh, int cbwh);

    [DllImport("winmm.dll")]
    private static extern int waveOutUnprepareHeader(IntPtr hwo, ref WAVEHDR pwh, int cbwh);

    [DllImport("winmm.dll")]
    private static extern int waveOutReset(IntPtr hwo);

    [DllImport("winmm.dll")]
    private static extern int waveOutClose(IntPtr hwo);

    [DllImport("winmm.dll")]
    private static extern int waveInOpen(out IntPtr phwi, int uDeviceID, ref WAVEFORMATEX pwfx, IntPtr dwCallback, IntPtr dwInstance, int fdwOpen);

    [DllImport("winmm.dll")]
    private static extern int waveInPrepareHeader(IntPtr hwi, ref WAVEHDR pwh, int cbwh);

    [DllImport("winmm.dll")]
    private static extern int waveInAddBuffer(IntPtr hwi, ref WAVEHDR pwh, int cbwh);

    [DllImport("winmm.dll")]
    private static extern int waveInStart(IntPtr hwi);

    [DllImport("winmm.dll")]
    private static extern int waveInStop(IntPtr hwi);

    [DllImport("winmm.dll")]
    private static extern int waveInReset(IntPtr hwi);

    [DllImport("winmm.dll")]
    private static extern int waveInUnprepareHeader(IntPtr hwi, ref WAVEHDR pwh, int cbwh);

    [DllImport("winmm.dll")]
    private static extern int waveInClose(IntPtr hwi);

    public class DeviceInfo
    {
        public int Id;
        public string Name;
        public string Kind;
    }

    public static List<DeviceInfo> ListDevices()
    {
        var list = new List<DeviceInfo>();
        int nOut = waveOutGetNumDevs();
        for (int i = 0; i < nOut; i++)
        {
            var caps = new WAVEOUTCAPS();
            if (waveOutGetDevCaps(i, ref caps, Marshal.SizeOf(typeof(WAVEOUTCAPS))) == 0)
                list.Add(new DeviceInfo { Id = i, Name = caps.szPname ?? "", Kind = "render" });
        }
        int nIn = waveInGetNumDevs();
        for (int i = 0; i < nIn; i++)
        {
            var caps = new WAVEINCAPS();
            if (waveInGetDevCaps(i, ref caps, Marshal.SizeOf(typeof(WAVEINCAPS))) == 0)
                list.Add(new DeviceInfo { Id = i, Name = caps.szPname ?? "", Kind = "capture" });
        }
        return list;
    }

    public static int FindDevice(string fragment, bool render)
    {
        if (string.IsNullOrWhiteSpace(fragment))
            throw new ArgumentException("device fragment required");
        fragment = fragment.Trim();
        var list = ListDevices();
        var matches = new List<DeviceInfo>();
        foreach (var d in list)
        {
            if (render && d.Kind != "render") continue;
            if (!render && d.Kind != "capture") continue;
            if (d.Name.IndexOf(fragment, StringComparison.OrdinalIgnoreCase) >= 0)
                matches.Add(d);
        }
        if (matches.Count == 0)
            throw new InvalidOperationException(string.Format("no {0} device matching fragment '{1}'", render ? "render" : "capture", fragment));
        if (matches.Count > 1)
            throw new InvalidOperationException(string.Format("ambiguous {0} devices for '{1}': {2}", render ? "render" : "capture", fragment,
                string.Join("; ", matches.ConvertAll(m => m.Id + ":" + m.Name))));
        return matches[0].Id;
    }

  public class ProbeMetrics
    {
        public double Peak;
        public double Rms;
        public double? OnsetMs;
        public int SamplesRecorded;
        public string Verdict;
        public string Error;
    }

    private static WAVEFORMATEX MakePcmFormat(int sampleRate, short bits, short channels)
    {
        ushort blockAlign = (ushort)(channels * bits / 8);
        return new WAVEFORMATEX
        {
            wFormatTag = WAVE_FORMAT_PCM,
            nChannels = (ushort)channels,
            nSamplesPerSec = (uint)sampleRate,
            nAvgBytesPerSec = (uint)(sampleRate * blockAlign),
            nBlockAlign = blockAlign,
            wBitsPerSample = (ushort)bits,
            cbSize = 0
        };
    }

    private static byte[] BuildToneBuffer(int sampleRate, double toneMs, double level)
    {
        int toneSamples = Math.Max(1, (int)(sampleRate * toneMs / 1000.0));
        var data = new byte[toneSamples * 2];
        double phase = 0;
        double phaseInc = 2.0 * Math.PI * 1000.0 / sampleRate;
        short amp = (short)Math.Round(level * 32767.0);
        for (int i = 0; i < toneSamples; i++)
        {
            short s = (short)(Math.Sin(phase) * amp);
            phase += phaseInc;
            data[i * 2] = (byte)(s & 0xFF);
            data[i * 2 + 1] = (byte)((s >> 8) & 0xFF);
        }
        return data;
    }

    private static ProbeMetrics AnalyzePcm16(byte[] raw, int sampleRate, double onsetThreshold, double passPeakMin, int toneSamples)
    {
        var m = new ProbeMetrics { SamplesRecorded = raw.Length / 2 };
        if (m.SamplesRecorded == 0)
        {
            m.Verdict = "FAIL";
            m.Error = "no samples";
            return m;
        }
        double sumSq = 0;
        double peak = 0;
        int? onset = null;
        for (int i = 0; i < m.SamplesRecorded; i++)
        {
            int off = i * 2;
            short s = (short)(raw[off] | (raw[off + 1] << 8));
            double v = s / 32768.0;
            double av = Math.Abs(v);
            if (av > peak) peak = av;
            sumSq += v * v;
            if (!onset.HasValue && av >= onsetThreshold)
                onset = i;
        }
        m.Peak = peak;
        m.Rms = Math.Sqrt(sumSq / m.SamplesRecorded);
        if (onset.HasValue)
            m.OnsetMs = onset.Value * 1000.0 / sampleRate;
        else
            m.OnsetMs = null;
        m.Verdict = peak > passPeakMin ? "PASS" : "FAIL";
        return m;
    }

    public static ProbeMetrics RunLoopback(int outId, int inId, int sampleRate, double toneMs, double captureSec, double toneLevel, double onsetThreshold, double passPeakMin, int timeoutMs)
    {
        var fmt = MakePcmFormat(sampleRate, 16, 1);
        int toneSamples = Math.Max(1, (int)(sampleRate * toneMs / 1000.0));
        int capSamples = Math.Max(toneSamples, (int)(sampleRate * captureSec));
        int capBytes = capSamples * 2;
        byte[] tone = BuildToneBuffer(sampleRate, toneMs, toneLevel);
        byte[] capBuf = new byte[capBytes];

        GCHandle tonePin = GCHandle.Alloc(tone, GCHandleType.Pinned);
        GCHandle capPin = GCHandle.Alloc(capBuf, GCHandleType.Pinned);
        IntPtr hOut = IntPtr.Zero;
        IntPtr hIn = IntPtr.Zero;
        var whOut = new WAVEHDR();
        var whIn = new WAVEHDR();
        try
        {
            int mm = waveOutOpen(out hOut, outId, ref fmt, IntPtr.Zero, IntPtr.Zero, CALLBACK_NULL);
            if (mm != 0) throw new InvalidOperationException("waveOutOpen failed: " + mm);
            mm = waveInOpen(out hIn, inId, ref fmt, IntPtr.Zero, IntPtr.Zero, CALLBACK_NULL);
            if (mm != 0) throw new InvalidOperationException("waveInOpen failed: " + mm);

            whIn.lpData = capPin.AddrOfPinnedObject();
            whIn.dwBufferLength = (uint)capBytes;
            whIn.dwFlags = 0;
            mm = waveInPrepareHeader(hIn, ref whIn, Marshal.SizeOf(typeof(WAVEHDR)));
            if (mm != 0) throw new InvalidOperationException("waveInPrepareHeader failed: " + mm);
            mm = waveInAddBuffer(hIn, ref whIn, Marshal.SizeOf(typeof(WAVEHDR)));
            if (mm != 0) throw new InvalidOperationException("waveInAddBuffer failed: " + mm);
            mm = waveInStart(hIn);
            if (mm != 0) throw new InvalidOperationException("waveInStart failed: " + mm);

            whOut.lpData = tonePin.AddrOfPinnedObject();
            whOut.dwBufferLength = (uint)tone.Length;
            whOut.dwFlags = 0;
            mm = waveOutPrepareHeader(hOut, ref whOut, Marshal.SizeOf(typeof(WAVEHDR)));
            if (mm != 0) throw new InvalidOperationException("waveOutPrepareHeader failed: " + mm);
            mm = waveOutWrite(hOut, ref whOut, Marshal.SizeOf(typeof(WAVEHDR)));
            if (mm != 0) throw new InvalidOperationException("waveOutWrite failed: " + mm);

            var deadline = DateTime.UtcNow.AddMilliseconds(timeoutMs);
            while ((whOut.dwFlags & WHDR_DONE) == 0 && DateTime.UtcNow < deadline)
                Thread.Sleep(10);
            while ((whIn.dwFlags & WHDR_DONE) == 0 && DateTime.UtcNow < deadline)
                Thread.Sleep(10);
            if ((whIn.dwFlags & WHDR_DONE) == 0)
                throw new TimeoutException("capture timeout");

            waveOutReset(hOut);
            waveInStop(hIn);
            waveInReset(hIn);

            int recorded = (int)whIn.dwBytesRecorded;
            if (recorded <= 0) recorded = capBytes;
            if (recorded > capBytes) recorded = capBytes;
            var slice = new byte[recorded];
            Array.Copy(capBuf, slice, recorded);
            return AnalyzePcm16(slice, sampleRate, onsetThreshold, passPeakMin, toneSamples);
        }
        finally
        {
            if (hOut != IntPtr.Zero)
            {
                try
                {
                    waveOutUnprepareHeader(hOut, ref whOut, Marshal.SizeOf(typeof(WAVEHDR)));
                    waveOutClose(hOut);
                }
                catch { }
            }
            if (hIn != IntPtr.Zero)
            {
                try
                {
                    waveInUnprepareHeader(hIn, ref whIn, Marshal.SizeOf(typeof(WAVEHDR)));
                    waveInClose(hIn);
                }
                catch { }
            }
            if (tonePin.IsAllocated) tonePin.Free();
            if (capPin.IsAllocated) capPin.Free();
        }
    }
}
'@
    Add-Type -TypeDefinition $csharp -Language CSharp -ErrorAction Stop
}

function Invoke-ProbePair {
    param(
        [string]$OutFragment,
        [string]$InFragment,
        [string]$LineLabel
    )
    if (-not $OutFragment -or -not $InFragment) {
        throw "需要 -Out 與 -In 名稱片段"
    }
    $outId = [AetherTuneVirtualLineProbe]::FindDevice($OutFragment, $true)
    $inId = [AetherTuneVirtualLineProbe]::FindDevice($InFragment, $false)
    $devices = [AetherTuneVirtualLineProbe]::ListDevices()
    $outName = ($devices | Where-Object { $_.Kind -eq 'render' -and $_.Id -eq $outId }).Name
    $inName = ($devices | Where-Object { $_.Kind -eq 'capture' -and $_.Id -eq $inId }).Name
    $metrics = [AetherTuneVirtualLineProbe]::RunLoopback(
        $outId, $inId, $SampleRate, $ToneMs, $CaptureSec, $ToneLevel, $OnsetThreshold, $PassPeakMin, $TimeoutMs
    )
    return [ordered]@{
        label        = $LineLabel
        out_fragment = $OutFragment
        in_fragment  = $InFragment
        out_id       = $outId
        in_id        = $inId
        out_name     = $outName
        in_name      = $inName
        peak         = $metrics.Peak
        rms          = $metrics.Rms
        onset_ms     = $metrics.OnsetMs
        verdict      = $metrics.Verdict
        error        = $metrics.Error
        played_level = $ToneLevel
        pass_peak_min = $PassPeakMin
        onset_threshold = $OnsetThreshold
    }
}

if ($List) {
    $devs = [AetherTuneVirtualLineProbe]::ListDevices()
    $renderN = @($devs | Where-Object { $_.Kind -eq 'render' }).Count
    $captureN = @($devs | Where-Object { $_.Kind -eq 'capture' }).Count
    $payload = @{
        timestamp_local = (Get-Date -Format 'yyyy-MM-ddTHH:mm:ss')
        note            = 'winmm names truncated to 31 chars; match by fragment'
        render_count    = $renderN
        capture_count   = $captureN
        devices         = @($devs | ForEach-Object {
            @{ id = $_.Id; kind = $_.Kind; name = $_.Name }
        })
    }
    Write-Output ($payload | ConvertTo-Json -Depth 5)
    exit 0
}

if (-not $Out -or -not $In) {
    Write-Error 'Probe 模式需要 -Out 與 -In（或改用 -List）。'
    exit 2
}

$stamp = Get-Date -Format 'yyyy-MM-ddTHH:mm:ss'
$result = [ordered]@{
    timestamp_local = $stamp
    probe           = (Invoke-ProbePair -OutFragment $Out -InFragment $In -LineLabel $Label)
    crosstalk       = $null
}

if ($Crosstalk) {
    if (-not $CrosstalkOut -or -not $CrosstalkIn) {
        Write-Error '-Crosstalk 需要 -CrosstalkOut 與 -CrosstalkIn。'
        exit 2
    }
    $xt = Invoke-ProbePair -OutFragment $Out -InFragment $CrosstalkIn -LineLabel 'crosstalk'
    $xt | Add-Member -NotePropertyName expect_silence -NotePropertyValue $true -Force
    if ($xt.peak -gt $PassPeakMin) {
        $xt.verdict = 'FAIL'
        $xt | Add-Member -NotePropertyName crosstalk_fail -NotePropertyValue $true -Force
    } else {
        $xt.verdict = 'PASS'
    }
    $result.crosstalk = $xt
}

$overall = $result.probe.verdict
if ($result.crosstalk -and $result.crosstalk.verdict -ne 'PASS') { $overall = 'FAIL' }

$result | Add-Member -NotePropertyName overall_verdict -NotePropertyValue $overall -Force

Write-Host ("[{0}] {1} -> {2}: peak={3:N4} rms={4:N4} onset={5} verdict={6}" -f `
    $Label, $result.probe.out_name, $result.probe.in_name, `
    $result.probe.peak, $result.probe.rms, `
    ($(if ($null -ne $result.probe.onset_ms) { '{0:N2} ms' -f $result.probe.onset_ms } else { 'n/a' })), `
    $result.probe.verdict)

if ($result.crosstalk) {
    Write-Host ("crosstalk {0}: peak={1:N4} verdict={2}" -f $result.crosstalk.in_name, $result.crosstalk.peak, $result.crosstalk.verdict)
}

if ($OutJson) {
    $dir = Split-Path -Parent $OutJson
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    ($result | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $OutJson -Encoding UTF8
    Write-Host "Wrote $OutJson"
}

if ($overall -ne 'PASS') { exit 1 }
exit 0