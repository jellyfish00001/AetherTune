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
} from './services/desktop';
import { SpeechWorkspace, type ShellWithQuickInput } from './components/SpeechWorkspace';
import './style.css';

const initial: Status = {
  value: 'OFFLINE',
  engine_id: null,
  reason: '尚未啟動。音訊驗收 WAITING。',
  audio_verified: false,
};
const modeLabels: Record<string, string> = {
  streaming_vc: 'Streaming VC',
  speech_reconstruction: 'Speech Reconstruction',
  text_to_speech: 'Text → Voice',
};
const capabilities: Record<string, string> = {
  streaming_vc: 'realtime_vc',
  speech_reconstruction: 'speech_reconstruction',
  text_to_speech: 'text_to_speech',
};
const ttsModes = new Set(['speech_reconstruction', 'text_to_speech']);

function App() {
  const defaultAppShell: ShellWithQuickInput = { ...defaultShell, quick_input: false };
  const [shell, setShell] = useState<ShellWithQuickInput>(defaultAppShell);
  const [manifests, setManifests] = useState<Manifest[]>(previewManifests);
  const [mode, setMode] = useState('streaming_vc');
  const [engine, setEngine] = useState('seed-vc');
  const [page, setPage] = useState('LIVE');
  const [status, setStatus] = useState<Status>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [validation, setValidation] = useState('');
  const [reference, setReference] = useState('D:\\AetherTune\\dataset\\reference-voices\\voice-female-f1.wav');
  const [source, setSource] = useState('D:\\AetherTune\\dataset\\reference-voices\\voice-male-m1.wav');
  const [input, setInput] = useState('麥克風 (HyperX QuadCast S)');
  const [output, setOutput] = useState('CABLE Input (VB-Audio Virtual Cable)');
  const [host, setHost] = useState('Windows DirectSound');
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
  const active = !!status.service_alive;
  const locked = active || busy;
  const implemented = selected.implementation === 'skeleton';
  const request = { reference, source, input, output, host_api: host, parameters: {} };

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
    setValidation('');
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

  const modes = <div className="window-modes" aria-label="視窗模式">{(['full', 'compact', 'mini'] as const).map((windowMode) => <button key={windowMode} aria-pressed={shell.mode === windowMode} onClick={() => void changeShell({ mode: windowMode, click_through: false, quick_input: false })}>{windowMode === 'full' ? 'Full' : windowMode === 'compact' ? 'Compact' : 'Mini'}</button>)}</div>;
  const controls = <div className="actions"><button className="start" disabled={!native || !implemented || active || busy} onClick={() => void start()}>▶ START</button><button disabled={!native || (!active && status.value === 'OFFLINE') || busy} onClick={() => void stop()}>■ STOP</button></div>;
  const meters = <div className="metrics"><div><span>LATENCY</span><strong>N/A <small>ms</small></strong></div><div><span>GPU</span><strong>N/A</strong></div><div><span>MIC / OUTPUT</span><strong className="waiting">WAITING</strong></div><div><span>STT</span><strong>OFFLINE</strong></div></div>;

  const speechProps = isSpeechMode ? {
    mode: mode as 'speech_reconstruction' | 'text_to_speech',
    onModeChange: changeMode,
    engineId: engine,
    onEngineChange: setEngine,
    shell,
    onShellPatch: changeShell,
    onError: setError,
    output,
    hostApi: host,
    onOutputChange: setOutput,
    onHostApiChange: setHost,
  } : null;
  const speechWorkspace = speechProps ? <SpeechWorkspace {...speechProps} /> : null;
  const speechSettings = speechProps ? <SpeechWorkspace {...speechProps} settingsOnly /> : null;
  const miniQuickWorkspace = speechProps ? <SpeechWorkspace {...speechProps} quickOnly /> : null;
  const overlaySettings = <section className="panel settings"><h1>Overlay &amp; shortcuts</h1><label>Opacity · {Math.round(shell.opacity * 100)}%<input aria-label="Opacity" type="range" min="0.45" max="1" step="0.01" value={shell.opacity} onChange={(event) => void changeShell({ opacity: Number(event.target.value) })}/></label><label className="check"><input type="checkbox" checked={shell.always_on_top} onChange={(event) => void changeShell({ always_on_top: event.target.checked })}/>Always on Top (Full)</label><label className="check"><input type="checkbox" checked={shell.locked} onChange={(event) => void changeShell({ locked: event.target.checked })}/>Lock Position</label><label>顯示／隱藏快捷鍵<input aria-label="Overlay hotkey" value={hotkeys.visibility_hotkey} onChange={(event) => setHotkeys({ ...hotkeys, visibility_hotkey: event.target.value })}/></label><label>Runner Start / Stop 快捷鍵<input aria-label="Voice hotkey" value={hotkeys.voice_hotkey} onChange={(event) => setHotkeys({ ...hotkeys, voice_hotkey: event.target.value })}/></label><button disabled={!native} onClick={() => void changeShell(hotkeys)}>儲存快捷鍵</button><details><summary>Diagnostics</summary><pre aria-label="Backend logs">{log.length ? log.map((entry) => JSON.stringify(entry)).join('\n') : '尚無 backend log'}</pre></details><button disabled={!native} onClick={() => void command('exit')}>Exit AetherTune</button></section>;

  return <main className={`shell ${shell.mode}`} style={{ opacity: shell.mode === 'full' ? 1 : shell.opacity }} data-native={native}>
    <header><div className="brand" onPointerDown={beginDrag} onPointerMove={updateDrag} onPointerUp={(event) => { updateDrag(event); if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); }}><span className="mark">≈</span><b>AetherTune</b><span className="version">DESKTOP · v0.1</span></div><div className="window-tools"><button aria-label="收進 Tray" disabled={!native} onClick={() => void command('hide')}>─</button><button aria-label="關閉至 Tray" disabled={!native} onClick={() => void command('hide')}>×</button></div></header>
    {shell.mode === 'mini' ? <>
      <div className="mini-row"><span className="dot"/><strong>{selected.name}</strong><span>{isSpeechMode ? 'TTS' : status.value}</span><span>N/A ms</span><span title="Mic WAITING">Mic ?</span><button disabled={!native || !implemented || busy || isSpeechMode} aria-label={active ? 'Stop runner' : 'Start runner'} onClick={() => void (active ? stop() : start())}>{active ? '■' : '▶'}</button><button className="mini-quick-trigger" disabled={!isSpeechMode} aria-label="開啟 TTS Quick Input" onClick={() => void changeShell({ quick_input: true })}>[T]</button><button aria-label="展開 Compact" onClick={() => void changeShell({ mode: 'compact', click_through: false, quick_input: false })}>↗</button></div>
      {isSpeechMode && shell.quick_input && miniQuickWorkspace}
      {error && <div role="alert" className="error">{error}</div>}
    </> : <>
      <div className="topline"><span className="tag">{native ? 'LOCAL DESKTOP' : '瀏覽器預覽 · 無程序控制'}</span>{modes}</div>
      {shell.mode === 'full' && <nav>{['LIVE', 'VOICE', 'TRANSCRIPT', 'AUDIO', 'SETTINGS'].map((tab) => <button key={tab} className={page === tab ? 'selected' : ''} onClick={() => setPage(tab)}>{tab}</button>)}</nav>}
      <div className="content">
        {(page === 'LIVE' || page === 'VOICE' || page === 'TRANSCRIPT' || shell.mode === 'compact') ? isSpeechMode ? speechWorkspace : <>
          <div className="headline"><div><span className="eyebrow">VOICE WORKSPACE</span><h1>{shell.mode === 'full' ? '讓聲音，準備就緒。' : modeLabels[mode]}</h1></div><span className="state"><i className="dot"/>{status.value}</span></div>
          <div className="live-grid"><section className="panel setup"><h2>Quick controls <span>M2 skeleton</span></h2>
            <label>Mode<select aria-label="Mode" disabled={locked} value={mode} onChange={(event) => changeMode(event.target.value)}>{Object.entries(modeLabels).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label>
            <label>Engine <span className="classification">{selected.classification}</span><select aria-label="Engine" disabled={locked} value={engine} onChange={(event) => { setEngine(event.target.value); setValidation(''); }}>{available.map((manifest) => <option key={manifest.id} value={manifest.id}>{manifest.name}</option>)}</select></label>
            {shell.mode === 'full' && <>
              <label>Voice / Reference WAV<input aria-label="Reference WAV" disabled={locked} value={reference} onChange={(event) => setReference(event.target.value)}/></label>
              {selected.adapter === 'file_runner' ? <label>Source WAV<input aria-label="Source WAV" disabled={locked} value={source} onChange={(event) => setSource(event.target.value)}/></label> : selected.adapter === 'temporary_gui' ? <div className="device-fields"><label>Host API<input aria-label="Host API" disabled={locked} value={host} onChange={(event) => setHost(event.target.value)}/></label><label>Input<input aria-label="Input" disabled={locked} value={input} onChange={(event) => setInput(event.target.value)}/></label><label>Output<input aria-label="Output" disabled={locked} value={output} onChange={(event) => setOutput(event.target.value)}/></label></div> : null}
            </>}
            <p className="adapter-label">{selected.adapter === 'temporary_gui' ? 'TEMPORARY · 官方 GUI；請在該 GUI 開啟音訊' : selected.adapter === 'file_runner' ? 'WAV runner · 即時音訊整合 WAITING' : 'PLANNED · 本輪僅描述契約'}</p>
            {controls}
            {shell.mode === 'full' && <button className="text-button" disabled={!native || !implemented || busy || active} onClick={() => void act(async () => { const result = await command<{ valid: boolean; events: { reason?: string; message?: string }[] }>('validate', { engine, request }); setValidation(`${result.valid ? '預檢 PASS · ' : '預檢 BLOCKED · '}${result.events.at(-1)?.reason ?? ''}`); })}>檢查啟動條件</button>}
            {validation && <p role="status" className="hint">{validation}</p>}
          </section><section className="panel monitoring"><h2>狀態監控 <span>AUDIO WAITING</span></h2>{meters}<p className="hint">{status.reason}</p><div className="route"><span>INPUT</span><b>{selected.adapter === 'file_runner' ? 'Source WAV' : input}</b><i>↓</i><b>{selected.name}</b><i>↓</i><span>OUTPUT</span><b>{selected.adapter === 'file_runner' ? 'artifacts/desktop/runs/' : output}</b></div><p className="hint">{selected.limitations.join(' ')}</p></section></div>
          <section className="panel transcript"><div><h2>Transcript</h2><span className="waiting">M4 · WAITING</span></div><p>ME / REMOTE 語音紀錄尚未啟用。切換 Engine 的流程預留獨立 STT service。</p></section>
        </> : page === 'SETTINGS' ? <>{isSpeechMode && speechSettings}{overlaySettings}</> : <section className="panel placeholder"><span className="eyebrow">{page}</span><h1>{page === 'VOICE' ? 'Voice Library' : page === 'AUDIO' ? 'Audio Device Registry' : 'Transcript History'}</h1><p>{page === 'VOICE' ? 'M5 · WAITING：VoiceProfile 尚未整合。' : page === 'AUDIO' ? 'WAITING：canonical Windows endpoint registry 尚未實作；Seed migration 使用現有 runner 核對 PortAudio 名稱。' : 'M4 · WAITING：SQLite、Mic／Remote VAD + STT 與匯出尚未啟用。'}</p></section>}
        {error && <div role="alert" className="error">{error}</div>}
      </div>
      <footer><span>ENGINE {selected.name} · {status.value}</span><span>音訊 WAITING</span><button disabled={!native} aria-pressed={shell.locked} onClick={() => void changeShell({ locked: !shell.locked })}>{shell.locked ? '解鎖位置' : '鎖定位置'}</button>{shell.mode !== 'full' && <button disabled={!native} aria-pressed={shell.click_through} onClick={() => void changeShell({ click_through: !shell.click_through })}>Click-through</button>}</footer>
    </>}
  </main>;
}

createRoot(document.getElementById('root')!).render(<App/>);
