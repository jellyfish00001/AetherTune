import React from 'react';
import { outputDeviceChoices, type AudioDevices, type SpeechRoute } from '../services/speech';
import type { VcPostFx } from '../services/desktop';

type Monitor = NonNullable<SpeechRoute['monitor']>;

const physicalDevice = (name: string) => !/CABLE|Voicemeeter|VB-Audio/i.test(name);

function numberValue(value: string, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function VcAudioControls({
  reference,
  onReference,
  showReference,
  showInput = true,
  input,
  onInput,
  output,
  onOutput,
  host,
  onHost,
  monitor,
  onMonitor,
  postfx,
  onPostfx,
  audioDevices,
  locked,
  native,
  showAllOutputs,
  onShowAllOutputs,
  audioDeviceError,
  audioDeviceBusy,
  onReloadAudioDevices,
}: {
  reference: string;
  onReference: (value: string) => void;
  showReference: boolean;
  showInput?: boolean;
  input: string;
  onInput: (value: string) => void;
  output: string;
  onOutput: (value: string) => void;
  host: string;
  onHost: (value: string) => void;
  monitor: Monitor;
  onMonitor: (monitor: Monitor) => void;
  postfx: VcPostFx;
  onPostfx: (postfx: VcPostFx) => void;
  audioDevices: AudioDevices | null;
  locked: boolean;
  native: boolean;
  showAllOutputs: boolean;
  onShowAllOutputs: (value: boolean) => void;
  audioDeviceError: string;
  audioDeviceBusy: boolean;
  onReloadAudioDevices: () => void;
}) {
  const hostApis = Array.from(new Set([
    ...(audioDevices?.inputs ?? []),
    ...(audioDevices?.outputs ?? []),
  ].map((device) => device.host_api)));
  const inputDevices = (audioDevices?.inputs ?? []).filter((device) => device.host_api === host);
  const outputDevices = (audioDevices?.outputs ?? []).filter((device) => device.host_api === host);
  const outputChoices = outputDeviceChoices(outputDevices, { output, host_api: host }, showAllOutputs);
  const monitorChoices = outputDeviceChoices(audioDevices?.outputs ?? [], monitor, showAllOutputs)
    .filter(({ device }) => device.selectable && physicalDevice(device.name));
  const selectedMonitor = monitorChoices.find(({ device }) => device.name === monitor.output && device.host_api === monitor.host_api);
  const virtualOutput = /CABLE|Voicemeeter|VB-Audio/i.test(output);

  const updateFx = <K extends keyof VcPostFx>(key: K, value: VcPostFx[K]) => onPostfx({ ...postfx, [key]: value });

  return <div className="rvc-controls vc-audio-controls">
    {showReference && <label>Voice / Reference WAV<input aria-label="Reference WAV" disabled={locked} value={reference} onChange={(event) => onReference(event.target.value)}/></label>}
    <div className="device-fields">
      <label>Host API<select aria-label="Host API" disabled={locked || !audioDevices} value={hostApis.includes(host) ? host : ''} onChange={(event) => {
        const nextHost = event.target.value;
        onHost(nextHost);
        onInput('');
        onOutput('');
      }}><option value="">選擇 Host API</option>{hostApis.map((api) => <option key={api} value={api}>{api}</option>)}</select></label>
      {showInput && <label>麥克風／輸入裝置<select aria-label="Input device" disabled={locked || !audioDevices} value={inputDevices.some((device) => device.name === input && device.selectable) ? input : ''} onChange={(event) => onInput(event.target.value)}><option value="">選擇輸入裝置</option>{inputDevices.map((device, index) => <option key={`${device.name}-${index}`} value={device.name} disabled={!device.selectable}>{device.name}{device.is_default ? ' · 系統預設' : ''}{!device.selectable ? ' · 名稱重複' : ''}</option>)}</select></label>}
      <label>輸出裝置<select aria-label="Output device" disabled={locked || !audioDevices} value={outputChoices.some(({ device }) => device.name === output && device.selectable) ? output : ''} onChange={(event) => {
        const choice = outputChoices.find(({ device }) => device.name === event.target.value);
        if (choice?.device.selectable) onOutput(choice.device.name);
      }}><option value="">選擇輸出裝置</option>{outputChoices.map(({ device, index, label, isDefault }) => <option key={`${device.name}-${index}`} value={device.name} disabled={!device.selectable}>{label}{isDefault ? ' · 系統預設' : ''}{!device.selectable ? ' · 名稱重複' : ''}</option>)}</select></label>
      <label className="check"><input aria-label="VC 顯示進階輸出裝置" type="checkbox" checked={showAllOutputs} disabled={locked} onChange={(event) => onShowAllOutputs(event.target.checked)}/>顯示進階輸出裝置</label>
      <button type="button" className="text-button" disabled={audioDeviceBusy || !native} onClick={onReloadAudioDevices}>重新掃描裝置</button>
      {audioDeviceError && <p role="alert" className="error">裝置清單讀取失敗：{audioDeviceError}</p>}
    </div>

    <div className="composer-monitor">
      <label className="check"><input aria-label="自己監聽" type="checkbox" checked={monitor.enabled} disabled={!native || locked || monitorChoices.length === 0} onChange={(event) => {
        const preferred = (monitorChoices.find((choice) => choice.isDefault) ?? monitorChoices[0])?.device;
        onMonitor({ enabled: event.target.checked, output: monitor.output || preferred?.name || '', host_api: monitor.host_api || preferred?.host_api || '' });
      }}/>自己監聽</label>
      {monitor.enabled && <label>監聽裝置<select aria-label="監聽裝置" disabled={locked} value={selectedMonitor?.index ?? ''} onChange={(event) => {
        const device = monitorChoices.find((choice) => String(choice.index) === event.target.value)?.device;
        if (device) onMonitor({ enabled: true, output: device.name, host_api: device.host_api });
      }}><option value="">請選擇耳機或喇叭</option>{monitorChoices.map(({ index, device, label }) => <option key={`${device.name}-${device.host_api}`} value={index}>{label}</option>)}</select></label>}
      <p className="hint">{virtualOutput && !monitor.enabled ? '輸出送至虛擬線路；開啟自己監聽才能在耳機聽見。' : monitor.enabled ? '轉換後聲音會同時送到主輸出與監聽裝置。' : '自己監聽已關閉。'} 設定變更請先停止，再重新啟動。</p>
    </div>

    <details className="vc-postfx">
      <summary>音效與乾濕混合</summary>
      <label className="check"><input aria-label="啟用音效" type="checkbox" checked={postfx.enabled} disabled={locked} onChange={(event) => updateFx('enabled', event.target.checked)}/>啟用音效</label>
      <div className="device-fields">
        <label>乾濕混合<input aria-label="Post-FX wet" type="number" min={0} max={1} step={0.01} disabled={locked} value={postfx.wet} onChange={(event) => updateFx('wet', numberValue(event.target.value, postfx.wet))}/></label>
        <label>輸出增益（dB）<input aria-label="Post-FX output gain" type="number" min={-12} max={6} step={0.1} disabled={locked} value={postfx.output_gain_db} onChange={(event) => updateFx('output_gain_db', numberValue(event.target.value, postfx.output_gain_db))}/></label>
        <label>低頻（dB）<input aria-label="Post-FX low" type="number" min={-12} max={12} step={0.1} disabled={locked} value={postfx.low_db} onChange={(event) => updateFx('low_db', numberValue(event.target.value, postfx.low_db))}/></label>
        <label>中頻（dB）<input aria-label="Post-FX mid" type="number" min={-12} max={12} step={0.1} disabled={locked} value={postfx.mid_db} onChange={(event) => updateFx('mid_db', numberValue(event.target.value, postfx.mid_db))}/></label>
        <label>高頻（dB）<input aria-label="Post-FX high" type="number" min={-12} max={12} step={0.1} disabled={locked} value={postfx.high_db} onChange={(event) => updateFx('high_db', numberValue(event.target.value, postfx.high_db))}/></label>
        <label>Compressor threshold（dB）<input aria-label="Post-FX compressor threshold" type="number" min={-48} max={0} step={1} disabled={locked} value={postfx.compressor_threshold_db} onChange={(event) => updateFx('compressor_threshold_db', numberValue(event.target.value, postfx.compressor_threshold_db))}/></label>
        <label>Compressor ratio<input aria-label="Post-FX compressor ratio" type="number" min={1} max={8} step={0.1} disabled={locked} value={postfx.compressor_ratio} onChange={(event) => updateFx('compressor_ratio', numberValue(event.target.value, postfx.compressor_ratio))}/></label>
        <label>Reverb mix<input aria-label="Post-FX reverb mix" type="number" min={0} max={0.5} step={0.01} disabled={locked} value={postfx.reverb_mix} onChange={(event) => updateFx('reverb_mix', numberValue(event.target.value, postfx.reverb_mix))}/></label>
      </div>
      <p className="hint">關閉音效時保持原始轉換聲；乾濕比例控制「變聲後乾聲」與「音效處理聲」的混合，0 為純變聲後乾聲，1 為純音效處理聲。</p>
    </details>
  </div>;
}
