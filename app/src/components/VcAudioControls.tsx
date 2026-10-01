import { useI18n } from '../services/i18n';
import React from 'react';
import { outputDeviceChoices, type AudioDevices, type SpeechRoute } from '../services/speech';

type Monitor = NonNullable<SpeechRoute['monitor']>;

const physicalDevice = (name: string) => !/CABLE|Voicemeeter|VB-Audio/i.test(name);

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
  audioDevices: AudioDevices | null;
  locked: boolean;
  native: boolean;
  showAllOutputs: boolean;
  onShowAllOutputs: (value: boolean) => void;
  audioDeviceError: string;
  audioDeviceBusy: boolean;
  onReloadAudioDevices: () => void;
}) {
  const { t, diagnostic } = useI18n();
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

  return <div className="rvc-controls vc-audio-controls">
    {showReference && <label>{t("Voice / Reference WAV")}<input data-testid="control:Reference WAV" aria-label={t("Reference WAV")} disabled={locked} value={reference} onChange={(event) => onReference(event.target.value)}/></label>}
    <div className="device-fields">
      <label>{t("Host API")}<select data-testid="control:Host API" aria-label={t("Host API")} disabled={locked || !audioDevices} value={hostApis.includes(host) ? host : ''} onChange={(event) => {
        const nextHost = event.target.value;
        onHost(nextHost);
        onInput('');
        onOutput('');
      }}><option value="">{t("選擇 Host API")}</option>{hostApis.map((api) => <option key={api} value={api}>{api}</option>)}</select></label>
      {showInput && <label>{t("麥克風／輸入裝置")}<select data-testid="control:Input device" aria-label={t("Input device")} disabled={locked || !audioDevices} value={inputDevices.some((device) => device.name === input && device.selectable) ? input : ''} onChange={(event) => onInput(event.target.value)}><option value="">{t("選擇輸入裝置")}</option>{inputDevices.map((device, index) => <option key={`${device.name}-${index}`} value={device.name} disabled={!device.selectable}>{device.name}{device.is_default ? t(' · 系統預設') : ''}{!device.selectable ? t(' · 名稱重複') : ''}</option>)}</select></label>}
      <label>{t("輸出裝置")}<select data-testid="control:Output device" aria-label={t("Output device")} disabled={locked || !audioDevices} value={outputChoices.some(({ device }) => device.name === output && device.selectable) ? output : ''} onChange={(event) => {
        const choice = outputChoices.find(({ device }) => device.name === event.target.value);
        if (choice?.device.selectable) onOutput(choice.device.name);
      }}><option value="">{t("選擇輸出裝置")}</option>{outputChoices.map(({ device, index, label, isDefault }) => <option key={`${device.name}-${index}`} value={device.name} disabled={!device.selectable}>{label}{isDefault ? t(' · 系統預設') : ''}{!device.selectable ? t(' · 名稱重複') : ''}</option>)}</select></label>
      <label className="check"><input data-testid="control:VC 顯示進階輸出裝置" aria-label={t("VC 顯示進階輸出裝置")} type="checkbox" checked={showAllOutputs} disabled={locked} onChange={(event) => onShowAllOutputs(event.target.checked)}/>{t("顯示進階輸出裝置")}</label>
      <button type="button" className="text-button" disabled={audioDeviceBusy || !native} onClick={onReloadAudioDevices}>{t("重新掃描裝置")}</button>
      {audioDeviceError && <p role="alert" className="error">{t('裝置清單讀取失敗：')}{diagnostic(audioDeviceError)}</p>}
    </div>

    <div className="composer-monitor">
      <label className="check"><input data-testid="control:自己監聽" aria-label={t("自己監聽")} type="checkbox" checked={monitor.enabled} disabled={!native || locked || monitorChoices.length === 0} onChange={(event) => {
        const preferred = (monitorChoices.find((choice) => choice.isDefault) ?? monitorChoices[0])?.device;
        onMonitor({ enabled: event.target.checked, output: monitor.output || preferred?.name || '', host_api: monitor.host_api || preferred?.host_api || '' });
      }}/>{t("自己監聽")}</label>
      {monitor.enabled && <label>{t("監聽裝置")}<select data-testid="control:監聽裝置" aria-label={t("監聽裝置")} disabled={locked} value={selectedMonitor?.index ?? ''} onChange={(event) => {
        const device = monitorChoices.find((choice) => String(choice.index) === event.target.value)?.device;
        if (device) onMonitor({ enabled: true, output: device.name, host_api: device.host_api });
      }}><option value="">{t("請選擇耳機或喇叭")}</option>{monitorChoices.map(({ index, device, label }) => <option key={`${device.name}-${device.host_api}`} value={index}>{label}</option>)}</select></label>}
      <p className="hint">{t(virtualOutput && !monitor.enabled ? '輸出送至虛擬線路；開啟自己監聽才能在耳機聽見。' : monitor.enabled ? '轉換後聲音會同時送到主輸出與監聽裝置。' : '自己監聽已關閉。')} {t('設定變更請先停止，再重新啟動。')}</p>
    </div>

  </div>;
}
