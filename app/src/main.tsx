import { useI18n, LanguageProvider, LanguageSettings } from './services/i18n';
import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  command,
  defaultShell,
  native,
  previewManifests,
  subscribe,
  type Manifest,
  type Status,
  type VcPostFx,
} from './services/desktop';
import { SpeechWorkspace, type ShellWithQuickInput } from './components/SpeechWorkspace';
import { RvcControls, defaultRvcParameters } from './components/RvcControls';
import { EngineParameters } from './components/EngineParameters';
import { LoadStatus } from './components/LoadStatus';
import { SpeechMiniStatus } from './components/SpeechMiniStatus';
import { readEngineParameters, readNoiseRecords, normalizeNoiseReduction, defaultNoiseReduction, engineParameterError, type EngineParametersRecords } from './services/vc-settings';
import { VcAudioControls } from './components/VcAudioControls';
import { AudioEffectsSettings } from './components/AudioEffectsSettings';
import { audioEffectsStorageKey, defaultAudioEffects, normalizeAudioEffects, readAudioEffects } from './services/audio-effects';
import { getAudioDevices, outputDeviceChoices, type AudioDevices, type SpeechRoute } from './services/speech';
import './style.css';

const initial: Status = {
  value: 'OFFLINE',
  engine_id: null,
  reason: '尚未啟動。音訊驗收 WAITING。',
  audio_verified: false,
};
const modeLabels: Record<string, string> = {
  streaming_vc: 'Streaming VC',
  speech_reconstruction: 'Speech Reconstruction（目前僅文字）',
  text_to_speech: 'Text → Voice',
};
const capabilities: Record<string, string> = {
  streaming_vc: 'realtime_vc',
  speech_reconstruction: 'speech_reconstruction',
  text_to_speech: 'text_to_speech',
};
const ttsModes = new Set(['speech_reconstruction', 'text_to_speech']);
const vcSettingsStorageKey = 'aethertune.vc-settings.v1';
type VcMonitor = NonNullable<SpeechRoute['monitor']>;
type StoredVcSettings = {
  reference?: string;
  source?: string;
  input?: string;
  output?: string;
  host_api?: string;
  rvcParameters?: Record<string, string | number>;
  engineParameters?: EngineParametersRecords;
  noiseReduction?: ReturnType<typeof readNoiseRecords>;
  monitor?: VcMonitor;
  postfx?: VcPostFx;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function optionalString(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function normalizeMonitor(value: unknown): VcMonitor | undefined {
  if (!isRecord(value) || typeof value.enabled !== 'boolean') return undefined;
  return {
    enabled: value.enabled,
    output: optionalString(value.output) ?? '',
    host_api: optionalString(value.host_api) ?? '',
  };
}

function normalizePostFx(value: unknown): VcPostFx | undefined {
  if (!isRecord(value)) return undefined;
  return normalizeAudioEffects(value);
}

function normalizeRvcParameters(value: unknown): Record<string, string | number> | undefined {
  if (!isRecord(value)) return undefined;
  const result: Record<string, string | number> = {};
  for (const [name, fallback] of Object.entries(defaultRvcParameters)) {
    const stored = value[name];
    if (typeof fallback === 'number') {
      if (typeof stored === 'number' && Number.isFinite(stored)) result[name] = stored;
      else result[name] = fallback;
    } else {
      result[name] = typeof stored === 'string' ? stored : fallback;
    }
  }
  return result;
}

function readVcSettings(): StoredVcSettings {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(vcSettingsStorageKey);
    if (!raw) return {};
    const value: unknown = JSON.parse(raw);
    if (!isRecord(value)) return {};
    const route = isRecord(value.route) ? value.route : value;
    return {
      reference: optionalString(value.reference),
      source: optionalString(value.source),
      input: optionalString(route.input),
      output: optionalString(route.output),
      host_api: optionalString(route.host_api),
      rvcParameters: normalizeRvcParameters(value.rvcParameters),
      engineParameters: readEngineParameters(value.engineParameters, value.rvcParameters),
      noiseReduction: readNoiseRecords(value.noiseReduction),
      monitor: normalizeMonitor(value.monitor),
      postfx: normalizePostFx(value.postfx),
    };
  } catch {
    return {};
  }
}

function isPhysicalAudioDevice(name: string): boolean {
  return !/CABLE|Voicemeeter|VB-Audio/i.test(name);
}

function isOutputAlias(name: string): boolean {
  return /^(Microsoft (Sound Mapper|音效對應表) - Output|Primary Sound Driver|主要音效驅動程式)$/i.test(name.trim());
}

function isSelectablePhysicalOutput(device: AudioDevices['outputs'][number]): boolean {
  return device.selectable && isPhysicalAudioDevice(device.name) && !isOutputAlias(device.name);
}

function hasSelectableDevice(devices: AudioDevices, direction: 'inputs' | 'outputs', name: string, hostApi: string): boolean {
  return !!name && devices[direction].some((device) => device.selectable && device.name === name && device.host_api === hostApi);
}

function preferredHost(devices: AudioDevices, currentHost: string, currentInput: string, currentOutput: string): string {
  const hasPair = (hostApi: string) => devices.inputs.some((device) => device.selectable && device.host_api === hostApi)
    && devices.outputs.some((device) => device.selectable && device.host_api === hostApi);
  if (hasPair(currentHost)
    && hasSelectableDevice(devices, 'inputs', currentInput, currentHost)
    && hasSelectableDevice(devices, 'outputs', currentOutput, currentHost)) return currentHost;
  const hosts = Array.from(new Set([
    ...devices.inputs.filter((device) => device.selectable).map((device) => device.host_api),
    ...devices.outputs.filter((device) => device.selectable).map((device) => device.host_api),
  ]));
  const rank = (hostApi: string) => {
    const hasPhysical = devices.outputs.some((device) => device.host_api === hostApi && isSelectablePhysicalOutput(device));
    const index = ['Windows DirectSound', 'Windows WASAPI'].indexOf(hostApi);
    return (hasPhysical ? 0 : 10) + (index < 0 ? 99 : index);
  };
  return hosts.filter(hasPair).sort((left, right) => rank(left) - rank(right))[0] ?? '';
}

function preferredInput(devices: AudioDevices, hostApi: string, currentInput: string): string {
  const candidates = devices.inputs.filter((device) => device.selectable && device.host_api === hostApi);
  if (candidates.some((device) => device.name === currentInput)) return currentInput;
  return (candidates.find((device) => /HyperX/i.test(device.name))
    ?? candidates.find((device) => device.is_default && isPhysicalAudioDevice(device.name))
    ?? candidates.find((device) => isPhysicalAudioDevice(device.name))
    ?? candidates[0])?.name ?? '';
}

function preferredOutput(devices: AudioDevices, hostApi: string, currentOutput: string): string {
  const candidates = devices.outputs.filter((device) => device.selectable && device.host_api === hostApi);
  if (candidates.some((device) => device.name === currentOutput)) return currentOutput;
  const physical = candidates.filter(isSelectablePhysicalOutput);
  const localDefault = physical.find((device) => device.is_default);
  if (localDefault) return localDefault.name;
  const physicalNames = new Set(physical.map((device) => device.name.trim()));
  const crossApiDefault = devices.outputs.find((device) => device.host_api !== hostApi
    && device.is_default
    && isSelectablePhysicalOutput(device)
    && physicalNames.has(device.name.trim()));
  const corresponding = crossApiDefault && physical.find((device) => device.name.trim() === crossApiDefault.name.trim());
  if (corresponding) return corresponding.name;
  return (physical.find((device) => /HyperX/i.test(device.name))
    ?? physical[0]
    ?? candidates.find((device) => device.is_default)
    ?? candidates[0])?.name ?? '';
}

function App() {
  const { t, diagnostic } = useI18n();
  const defaultAppShell: ShellWithQuickInput = { ...defaultShell, quick_input: false };
  const [storedVcSettings] = useState(readVcSettings);
  const [shell, setShell] = useState<ShellWithQuickInput>(defaultAppShell);
  const [manifests, setManifests] = useState<Manifest[]>(previewManifests);
  const [mode, setMode] = useState('streaming_vc');
  const [engine, setEngine] = useState('rvc');
  const [page, setPage] = useState('LIVE');
  const [status, setStatus] = useState<Status>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [validation, setValidation] = useState<{ valid: boolean; reason: string } | null>(null);
  const [reference, setReference] = useState(storedVcSettings.reference ?? 'D:\\AetherTune\\dataset\\reference-voices\\voice-female-f1.wav');
  const [source, setSource] = useState(storedVcSettings.source ?? 'D:\\AetherTune\\dataset\\reference-voices\\voice-male-m1.wav');
  const [input, setInput] = useState(storedVcSettings.input ?? '');
  const [output, setOutput] = useState(storedVcSettings.output ?? '');
  const [host, setHost] = useState(storedVcSettings.host_api ?? '');
  const [engineParameters, setEngineParameters] = useState(() => storedVcSettings.engineParameters ?? readEngineParameters(undefined, storedVcSettings.rvcParameters));
  const rvcParameters = engineParameters.rvc;
  const [noiseReduction, setNoiseReduction] = useState(() => storedVcSettings.noiseReduction ?? readNoiseRecords(undefined));
  const [vcMonitor, setVcMonitor] = useState<VcMonitor>(storedVcSettings.monitor ?? { enabled: false, output: '', host_api: '' });
  const [audioEffects, setAudioEffects] = useState(() => readAudioEffects(storedVcSettings.postfx));
  const [effectsEngine, setEffectsEngine] = useState('rvc');
  const [effectsSaveError, setEffectsSaveError] = useState('');
  const [vcSaveError, setVcSaveError] = useState('');
  const [showAllVcOutputs, setShowAllVcOutputs] = useState(false);
  const [speechRoute, setSpeechRoute] = useState<SpeechRoute>({ output: '', host_api: '', monitor: { enabled: false, output: '', host_api: '' } });
  const [audioDevices, setAudioDevices] = useState<AudioDevices | null>(null);
  const [audioDeviceError, setAudioDeviceError] = useState('');
  const [audioDeviceBusy, setAudioDeviceBusy] = useState(false);
  const [log, setLog] = useState<Record<string, unknown>[]>([]);
  const [hotkeys, setHotkeys] = useState({
    visibility_hotkey: defaultShell.visibility_hotkey,
    voice_hotkey: defaultShell.voice_hotkey,
  });
  const pointerDrag = useRef<{ sx: number; sy: number; x: number; y: number; origin?: { x: number; y: number; scale: number } } | undefined>(undefined);

  function moveDrag() {
    const drag = pointerDrag.current;
    if (drag?.origin) {
      void command('move_window', {
        x: Math.round(drag.origin.x + (drag.x - drag.sx) * drag.origin.scale),
        y: Math.round(drag.origin.y + (drag.y - drag.sy) * drag.origin.scale),
      }).catch((reason) => setError(String(reason)));
    }
  }

  function beginDrag(event: React.PointerEvent<HTMLDivElement>) {
    if (!native || shell.locked || event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const drag = { sx: event.screenX, sy: event.screenY, x: event.screenX, y: event.screenY } as NonNullable<typeof pointerDrag.current>;
    pointerDrag.current = drag;
    void command<{ position: { x: number; y: number }; scale_factor: number }>('window_status').then((windowState) => {
      drag.origin = { ...windowState.position, scale: windowState.scale_factor };
      if (pointerDrag.current === drag) moveDrag();
    }).catch((reason) => setError(String(reason)));
  }

  function updateDrag(event: React.PointerEvent<HTMLDivElement>) {
    if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
    const drag = pointerDrag.current;
    if (drag) {
      drag.x = event.screenX;
      drag.y = event.screenY;
      moveDrag();
    }
  }

  const selected = manifests.find((manifest) => manifest.id === engine) ?? previewManifests.find((manifest) => manifest.id === engine) ?? previewManifests[0];
  const available = manifests.filter((manifest) => manifest.capabilities.includes(capabilities[mode]));
  const isSpeechMode = ttsModes.has(mode);
  const isStreamingVc = mode === 'streaming_vc';
  const active = !!status.service_alive;
  const locked = active || busy;
  const isRvc = engine === 'rvc';
  const postfx = audioEffects[engine] ?? defaultAudioEffects;
  const rvcFile = isRvc && rvcParameters.source_mode === 'file';
  const implemented = ['skeleton', 'implemented'].includes(selected.implementation);
  const request = { reference, source, input, output, host_api: host, parameters: engineParameters[engine] ?? {}, monitor: vcMonitor, postfx, noise_reduction: noiseReduction[engine] ?? defaultNoiseReduction };
  const parameterError = engineParameterError(engine, engineParameters[engine] ?? {});
  const inputDevices = (audioDevices?.inputs ?? []).filter((device) => device.host_api === host);
  const outputDevices = (audioDevices?.outputs ?? []).filter((device) => device.host_api === host);
  const monitorValid = !vcMonitor.enabled || (audioDevices?.outputs ?? []).some((device) => device.selectable && isPhysicalAudioDevice(device.name) && device.name === vcMonitor.output && device.host_api === vcMonitor.host_api);
  const vcRouteValid = !isStreamingVc || (!!audioDevices
    && (rvcFile || inputDevices.some((device) => device.name === input && device.selectable))
    && outputDevices.some((device) => device.name === output && device.selectable)
    && monitorValid && !parameterError);

  async function reloadAudioDevices() {
    setAudioDeviceBusy(true);
    setAudioDeviceError('');
    try {
      const next = await getAudioDevices();
      setAudioDevices(next);
      const nextHost = preferredHost(next, host, input, output);
      const nextInput = preferredInput(next, nextHost, input);
      const nextOutput = preferredOutput(next, nextHost, output);
      setHost(nextHost);
      setInput(nextInput);
      setOutput(nextOutput);
      setVcMonitor((previous) => {
        if (!previous.enabled || hasSelectableDevice(next, 'outputs', previous.output, previous.host_api)) return previous;
        return { ...previous, output: '', host_api: '' };
      });
      setSpeechRoute((previous) => {
        if (next.outputs.some((device) => device.selectable && device.name === previous.output && device.host_api === previous.host_api)) return previous;
        const choices = outputDeviceChoices(next.outputs);
        const preferred = (choices.find((choice) => choice.isDefault) ?? choices[0])?.device;
        return { ...previous, output: preferred?.name ?? '', host_api: preferred?.host_api ?? '' };
      });
    } catch (reason) {
      setAudioDevices(null);
      setAudioDeviceError(String(reason));
    } finally {
      setAudioDeviceBusy(false);
    }
  }

  async function act(fn: () => Promise<unknown>) {
    setError('');
    setBusy(true);
    try {
      await fn();
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function refresh() {
    setStatus(await command<Status>('status'));
  }

  async function changeShell(patch: Partial<ShellWithQuickInput>) {
    const next = { ...shell, ...patch };
    try {
      if (native) await command('set_shell', { shell: next });
      setShell(next);
    } catch (reason) {
      setError(String(reason));
    }
  }

  function changeMode(nextMode: string) {
    setMode(nextMode);
    const first = manifests.find((manifest) => manifest.capabilities.includes(capabilities[nextMode]));
    if (first) setEngine(first.id);
    setValidation(null);
  }

  function openSettings() {
    setEffectsEngine(engine);
    setPage('SETTINGS');
    if (shell.mode !== 'full') void changeShell({ mode: 'full', click_through: false, quick_input: false });
  }

  async function start() {
    await act(async () => setStatus(await command<Status>('start', { engine, request })));
  }

  async function stop() {
    await act(async () => setStatus(await command<Status>('stop')));
  }

  useEffect(() => {
    if (!native) return;
    let disposed = false;
    const cleanup: (() => void)[] = [];
    const register = async <T,>(name: string, callback: (value: T) => void) => {
      const off = await subscribe<T>(name, callback);
      if (disposed) off();
      else cleanup.push(off);
    };
    void act(async () => {
      setManifests(await command<Manifest[]>('discover'));
      const shellState = await command<ShellWithQuickInput>('shell_status');
      setShell({ ...shellState, quick_input: shellState.quick_input ?? false });
      setHotkeys({ visibility_hotkey: shellState.visibility_hotkey, voice_hotkey: shellState.voice_hotkey });
      await refresh();
      setLog(await command('logs'));
    });
    void register<Record<string, unknown>>('engine-event', (event) => {
      setLog((previous) => [...previous, event].slice(-500));
      void refresh();
    });
    void register<ShellWithQuickInput>('shell', (shellState) => setShell({ ...shellState, quick_input: shellState.quick_input ?? false }));
    void register<{ error?: string }>('engine-action', (event) => {
      if (event.error) setError(event.error);
      void refresh();
    });
    const timer = setInterval(() => void refresh().catch((reason) => setError(String(reason))), 1000);
    return () => {
      disposed = true;
      clearInterval(timer);
      cleanup.forEach((off) => off());
    };
  }, []);

  useEffect(() => {
    if (native) void reloadAudioDevices();
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(vcSettingsStorageKey, JSON.stringify({
        route: { input, output, host_api: host },
        reference,
        source,
        rvcParameters,
        engineParameters,
        noiseReduction,
        monitor: vcMonitor,
      }));
      setVcSaveError('');
    } catch {
      setVcSaveError('vc.saveError');
    }
  }, [input, output, host, reference, source, engineParameters, noiseReduction, vcMonitor]);

  useEffect(() => {
    try {
      window.localStorage.setItem(audioEffectsStorageKey, JSON.stringify(audioEffects));
      setEffectsSaveError('');
    } catch {
      setEffectsSaveError('音效紀錄儲存失敗；本次設定仍可使用，關閉 App 後可能遺失。');
    }
  }, [audioEffects]);

  const modes = <div className="window-modes" data-testid="control:視窗模式" aria-label={t("視窗模式")}>{(['full', 'compact', 'mini'] as const).map((windowMode) => <button key={windowMode} data-testid={`window-mode-${windowMode}`} aria-pressed={shell.mode === windowMode} onClick={() => void changeShell({ mode: windowMode, click_through: false, quick_input: false })}>{t(windowMode === 'full' ? 'Full' : windowMode === 'compact' ? 'Compact' : 'Mini')}</button>)}</div>;
  const controls = <div className="actions"><button className="start" disabled={!native || !implemented || !vcRouteValid || active || busy} onClick={() => void start()}>{t("▶ START")}</button><button disabled={!native || (!active && status.value === 'OFFLINE') || busy} onClick={() => void stop()}>{t("■ STOP")}</button></div>;
  const formatDb = (value: unknown, alreadyDb = false): string => {
    if (typeof value !== 'number' || !Number.isFinite(value)) return t('N/A');
    if (alreadyDb) return `${value.toFixed(1)} dB`;
    if (value === 0) return '-∞ dB';
    return `${(20 * Math.log10(Math.abs(value))).toFixed(1)} dB`;
  };
  const formatMs = (value: unknown): string => typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(1)} ms` : t('N/A');
  const metrics = status.metrics;
  const inputPeak = formatDb(metrics?.input_peak_db ?? metrics?.input_peak, metrics?.input_peak_db !== undefined);
  const outputPeak = formatDb(metrics?.output_peak_db ?? metrics?.output_peak, metrics?.output_peak_db !== undefined);
  const formatRtf = (value: unknown): string => typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(2)}×${value > 1 ? t(' · 較慢') : ''}` : t('N/A');
  const count = (value: unknown) => typeof value === 'number' ? value : t('N/A');
  const meters = <><div className="metrics"><div><span>{t('MODEL P95')}</span><strong>{formatMs(metrics?.p95_ms)}</strong></div><div><span>{t('RTF（速度比；>1 較慢）')}</span><strong>{formatRtf(metrics?.rtf)}</strong></div><div><span>GPU</span><strong>{status.runtime?.gpu ?? status.runtime?.device ?? t('N/A')}</strong></div><div><span>{t('INPUT PEAK')}</span><strong>{inputPeak}</strong></div><div><span>{t('OUTPUT PEAK')}</span><strong>{outputPeak}</strong></div></div><p className="hint">{t('metrics.note', { blocks: count(metrics?.blocks), inputDrops: count(metrics?.input_drops), outputDrops: count(metrics?.output_drops), underruns: count(metrics?.underruns) })}</p></>;

  const speechProps = isSpeechMode ? {
    mode: mode as 'speech_reconstruction' | 'text_to_speech',
    onModeChange: changeMode,
    engineId: engine,
    postfx,
    onEngineChange: setEngine,
    shell,
    onShellPatch: changeShell,
    onError: setError,
    route: speechRoute,
    onRouteChange: setSpeechRoute,
    audioDevices,
    audioDeviceError,
    audioDeviceBusy,
    onReloadAudioDevices: reloadAudioDevices,
  } : null;
  const speechWorkspace = speechProps ? <SpeechWorkspace {...speechProps} /> : null;
  const speechSettings = speechProps ? <SpeechWorkspace {...speechProps} settingsOnly /> : null;
  const miniQuickWorkspace = speechProps ? <SpeechWorkspace {...speechProps} quickOnly /> : null;
  const effectsSettings = <AudioEffectsSettings engine={effectsEngine} onEngine={setEffectsEngine} settings={audioEffects[effectsEngine] ?? defaultAudioEffects} onSettings={(next) => setAudioEffects((previous) => ({ ...previous, [effectsEngine]: normalizeAudioEffects(next) }))} noiseReduction={noiseReduction[effectsEngine]} onNoiseReduction={(next) => setNoiseReduction((previous) => ({ ...previous, [effectsEngine]: normalizeNoiseReduction(next) }))} saveError={effectsSaveError || (vcSaveError ? t(vcSaveError) : '')}/>;
  const overlaySettings = <section className="panel settings"><h1>{t("Overlay & shortcuts")}</h1><label>{t('Opacity')} · {Math.round(shell.opacity * 100)}%<input data-testid="control:Opacity" aria-label={t("Opacity")} type="range" min="0.45" max="1" step="0.01" value={shell.opacity} onChange={(event) => void changeShell({ opacity: Number(event.target.value) })}/></label><label className="check"><input type="checkbox" checked={shell.always_on_top} onChange={(event) => void changeShell({ always_on_top: event.target.checked })}/>{t("Always on Top (Full)")}</label><label className="check"><input type="checkbox" checked={shell.locked} onChange={(event) => void changeShell({ locked: event.target.checked })}/>{t("Lock Position")}</label><label>{t("顯示／隱藏快捷鍵")}<input data-testid="control:Overlay hotkey" aria-label={t("Overlay hotkey")} value={hotkeys.visibility_hotkey} onChange={(event) => setHotkeys({ ...hotkeys, visibility_hotkey: event.target.value })}/></label><label>{t("Runner Start / Stop 快捷鍵")}<input data-testid="control:Voice hotkey" aria-label={t("Voice hotkey")} value={hotkeys.voice_hotkey} onChange={(event) => setHotkeys({ ...hotkeys, voice_hotkey: event.target.value })}/></label><button disabled={!native} onClick={() => void changeShell(hotkeys)}>{t("儲存快捷鍵")}</button><details><summary>{t("Diagnostics")}</summary><pre data-testid="control:Backend logs" aria-label={t("Backend logs")}>{log.length ? log.map((entry) => JSON.stringify(entry)).join('\n') : t('尚無 backend log')}</pre></details><button disabled={!native} onClick={() => void command('exit')}>{t("Exit AetherTune")}</button></section>;

  return <main className={`shell ${shell.mode}`} style={{ opacity: shell.mode === 'full' ? 1 : shell.opacity }} data-native={native}>
    <header><div className="brand" onPointerDown={beginDrag} onPointerMove={updateDrag} onPointerUp={(event) => { updateDrag(event); if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); }}><span className="mark">≈</span><b>AetherTune</b><span className="version">{t("DESKTOP · v0.1")}</span></div><div className="window-tools"><button data-testid="control:收進 Tray" aria-label={t("收進 Tray")} disabled={!native} onClick={() => void command('hide')}>─</button><button data-testid="control:關閉至 Tray" aria-label={t("關閉至 Tray")} disabled={!native} onClick={() => void command('hide')}>×</button></div></header>
    {shell.mode === 'mini' ? <>
      <div className="mini-row"><span className="dot"/><strong title={selected.name}>{isRvc ? 'RVC' : selected.name}</strong><span>{isSpeechMode ? 'TTS' : t(status.value)}</span>{isSpeechMode && <SpeechMiniStatus engine={engine}/>}{!isSpeechMode && <LoadStatus engine={engine} parameters={engineParameters[engine]} progress={status.progress} active={active} minimal/>}{!isSpeechMode && <span>{formatMs(status.metrics?.p95_ms)}</span>}<span title={isSpeechMode ? t('輸入文字後播放') : rvcFile ? source : input}>{isSpeechMode ? t('文字') : rvcFile ? 'WAV' : t('Mic')}</span><button disabled={!native || !implemented || !vcRouteValid || busy || isSpeechMode} aria-label={t(active ? 'Stop runner' : 'Start runner')} onClick={() => void (active ? stop() : start())}>{active ? '■' : '▶'}</button>{isSpeechMode && <button className="mini-quick-trigger" data-testid="control:開啟 TTS Quick Input" aria-label={t("開啟 TTS Quick Input")} onClick={() => void changeShell({ quick_input: true })}>[T]</button>}<button data-testid="control:展開 Compact" aria-label={t("展開 Compact")} onClick={() => void changeShell({ mode: 'compact', click_through: false, quick_input: false })}>↗</button></div>
      {isSpeechMode && shell.quick_input && miniQuickWorkspace}
    {error && <div role="alert" className="error">{diagnostic(error)}</div>}
    </> : <>
      <div className="topline"><span className="tag">{t(native ? 'LOCAL DESKTOP' : '瀏覽器預覽 · 無程序控制')}</span>{modes}</div>
      {shell.mode === 'full' && <nav>{[{ id: 'LIVE', label: 'WORKSPACE' }, { id: 'SETTINGS', label: 'SETTINGS' }].map((tab) => <button key={tab.id} data-testid={`nav-${tab.id}`} className={page === tab.id ? 'selected' : ''} onClick={() => tab.id === 'SETTINGS' ? openSettings() : setPage(tab.id)}>{t(tab.label)}</button>)}</nav>}
      <div className="content">
        {(page === 'LIVE' || shell.mode === 'compact') ? isSpeechMode ? speechWorkspace : <>
          <div className="headline"><div><span className="eyebrow">{t("VOICE WORKSPACE")}</span><h1>{t(shell.mode === 'full' ? '讓聲音，準備就緒。' : modeLabels[mode])}</h1></div><span className="state"><i className="dot"/>{t(status.value)}</span></div>
          <div className="live-grid"><section className="panel setup"><h2>{t("變聲控制")}</h2>
            <label>{t("Mode")}<select data-testid="control:Mode" aria-label={t("Mode")} disabled={locked} value={mode} onChange={(event) => changeMode(event.target.value)}>{Object.entries(modeLabels).map(([key, value]) => <option key={key} value={key}>{t(value)}</option>)}</select></label>
            <label>{t("Engine")}<span className="classification">{t(selected.classification)}</span><select data-testid="control:Engine" aria-label={t("Engine")} disabled={locked} value={engine} onChange={(event) => { setEngine(event.target.value); setValidation(null); }}>{available.map((manifest) => <option key={manifest.id} value={manifest.id}>{manifest.name}</option>)}</select></label>
            <p className="adapter-label">{t(rvcFile ? '來源 WAV 模式 · START 轉換並播放音檔，不讀取麥克風。' : '麥克風模式 · START 後等待 RUNNING，再開始說話；STOP 後可切換引擎。')}</p>
            <LoadStatus engine={engine} parameters={engineParameters[engine]} progress={status.progress} active={active}/>
            {controls}
            <button type="button" className="text-button" data-testid="control:調整音效" aria-label={t("調整音效")} onClick={openSettings}>{t('effects.entry', { state: t(postfx.enabled ? '已啟用' : '關閉') })}</button>
            {shell.mode === 'full' && <>
              {isStreamingVc && <EngineParameters manifest={selected} parameters={engineParameters[engine] ?? {}} onParameters={(next) => setEngineParameters((previous) => ({ ...previous, [engine]: next }))} locked={locked}/>}
              {parameterError && <p role="alert" className="error">{t(parameterError)}</p>}
              {vcSaveError && <p role="alert" className="error">{t(vcSaveError)}</p>}
              {isStreamingVc && <VcAudioControls reference={reference} onReference={setReference} showReference={!isRvc} showInput={!rvcFile} input={input} onInput={setInput} output={output} onOutput={setOutput} host={host} onHost={setHost} monitor={vcMonitor} onMonitor={setVcMonitor} audioDevices={audioDevices} locked={locked} native={native} showAllOutputs={showAllVcOutputs} onShowAllOutputs={setShowAllVcOutputs} audioDeviceError={audioDeviceError} audioDeviceBusy={audioDeviceBusy} onReloadAudioDevices={() => void reloadAudioDevices()}/>}
              {isRvc && rvcFile && <label>{t("Source WAV")}<input data-testid="control:Source WAV" aria-label={t("Source WAV")} disabled={locked} value={source} onChange={(event) => setSource(event.target.value)}/></label>}
            </>}
            {shell.mode === 'full' && <button className="text-button" disabled={!native || !implemented || !vcRouteValid || busy || active} onClick={() => void act(async () => { const result = await command<{ valid: boolean; events: { reason?: string; message?: string }[] }>('validate', { engine, request }); setValidation({ valid: result.valid, reason: result.events.at(-1)?.reason ?? '' }); })}>{t("檢查啟動條件")}</button>}
            {validation && <p role="status" className="hint">{t(validation.valid ? '預檢 PASS · ' : '預檢 BLOCKED · ')}{diagnostic(validation.reason)}</p>}
          </section><section className="panel monitoring"><h2>{t("串流狀態")}</h2>{meters}<details><summary>{t('backend.detail')}</summary><p className="hint">{diagnostic(status.reason)}</p></details><div className="route"><span>{t('INPUT')} · {host || t('未選擇 Host API')}</span><b>{isRvc && rvcFile ? `${t('Source WAV')} · ${source}` : input || t('未選擇輸入裝置')}</b><i>↓</i><b>{selected.name}</b><i>↓</i><span>{t('OUTPUT')} · {host || t('未選擇 Host API')}</span><b>{output || t('未選擇輸出裝置')}</b></div><details><summary>{t("驗收與使用限制")}</summary><p className="hint">{selected.limitations.map((note) => t(note)).join(' ')} {t('即時字幕／ME／REMOTE 語音紀錄尚未提供。')}</p></details></section></div>
        </> : <><LanguageSettings/>{effectsSettings}{isSpeechMode && speechSettings}{overlaySettings}</>}
        {error && <div role="alert" className="error">{diagnostic(error)}</div>}
      </div>
      <footer><span>{t('ENGINE')} {selected.name} · {t(isSpeechMode ? '文字發聲' : status.value)}</span>{!isSpeechMode && <span>{t(rvcFile ? '來源 WAV' : '麥克風輸入')}</span>}<button disabled={!native} aria-pressed={shell.locked} onClick={() => void changeShell({ locked: !shell.locked })}>{t(shell.locked ? '解鎖位置' : '鎖定位置')}</button>{shell.mode !== 'full' && <button disabled={!native} aria-pressed={shell.click_through} onClick={() => void changeShell({ click_through: !shell.click_through })}>{t("Click-through")}</button>}</footer>
    </>}
  </main>;
}

createRoot(document.getElementById('root')!).render(<LanguageProvider><App/></LanguageProvider>);
