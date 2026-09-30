import React from 'react';
import manifest from '../../../contracts/engines/rvc.json';
import { outputDeviceChoices, type AudioDevices, type SpeechRoute } from '../services/speech';

export const defaultRvcParameters = Object.fromEntries(manifest.parameters.map((parameter) => [parameter.name, parameter.default])) as Record<string, string | number>;
type Monitor = NonNullable<SpeechRoute['monitor']>;

export function RvcControls({ parameters, onParameters, monitor, onMonitor, audioDevices, locked, native }: {
  parameters: Record<string, string | number>;
  onParameters: (parameters: Record<string, string | number>) => void;
  monitor: Monitor;
  onMonitor: (monitor: Monitor) => void;
  audioDevices: AudioDevices | null;
  locked: boolean;
  native: boolean;
}) {
  const choices = outputDeviceChoices(audioDevices?.outputs ?? [], monitor).filter(({ device }) => !/CABLE|Voicemeeter|VB-Audio/i.test(device.name));
  const selected = choices.find(({ device }) => device.name === monitor.output && device.host_api === monitor.host_api);
  const labels: Record<string, string> = { microphone: '麥克風即時變聲', file: '來源 WAV 測試', fcpe: 'FCPE', rmvpe: 'RMVPE' };
  const field = (parameter: typeof manifest.parameters[number]) => <label key={parameter.name}>{parameter.label}
    {parameter.type === 'select' ? <select aria-label={`RVC ${parameter.name}`} disabled={locked} value={parameters[parameter.name]} onChange={(event) => onParameters({ ...parameters, [parameter.name]: event.target.value })}>
      {parameter.options?.map((option) => <option value={option} key={option}>{labels[option] ?? option}</option>)}
    </select> : <input aria-label={`RVC ${parameter.name}`} disabled={locked} type="number" min={parameter.min} max={parameter.max} step={parameter.step} value={parameters[parameter.name]} onChange={(event) => onParameters({ ...parameters, [parameter.name]: event.target.value === '' ? '' : Number(event.target.value) })}/>}
  </label>;
  return <div className="rvc-controls">
    <div className="device-fields">{manifest.parameters.filter((parameter) => parameter.level === 'basic').map(field)}</div>
    <details><summary>RVC 進階參數</summary><div className="device-fields">{manifest.parameters.filter((parameter) => parameter.level === 'advanced').map(field)}</div></details>
    <div className="composer-monitor">
      <label className="check"><input aria-label="RVC 自己監聽" type="checkbox" checked={monitor.enabled} disabled={!native || locked || choices.length === 0} onChange={(event) => {
        const target = (choices.find((choice) => choice.isDefault) ?? choices[0])?.device;
        onMonitor({ enabled: event.target.checked, output: monitor.output || target?.name || '', host_api: monitor.host_api || target?.host_api || '' });
      }}/>自己監聽</label>
      {monitor.enabled && <label>監聽裝置<select aria-label="RVC 監聽裝置" disabled={locked} value={selected?.index ?? ''} onChange={(event) => {
        const device = choices.find((choice) => String(choice.index) === event.target.value)?.device;
        if (device) onMonitor({ enabled: true, output: device.name, host_api: device.host_api });
      }}><option value="">請選擇耳機或喇叭</option>{choices.map(({ index, device, label }) => <option key={`${device.name}-${device.host_api}`} value={index}>{label}</option>)}</select></label>}
      <p className="hint">監聽預設關閉。主輸出選虛擬線路可避免直接聽見自己；設定變更請先停止，再重新啟動。</p>
    </div>
  </div>;
}
