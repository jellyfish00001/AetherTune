import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { native, type Shell } from '../services/desktop';
import {
  defaultSpeechSnapshot,
  getSpeechStatus,
  normalizeSpeechSnapshot,
  sendSpeechAction,
  subscribeSpeech,
  type InterruptPolicy,
  type SpeechAction,
  type SpeechInputSource,
  type SpeechQueueItem,
  type SpeechSettings,
  type SpeechSnapshot,
  type SpeechState,
  type VoiceProfile,
  type AudioDevices,
} from '../services/speech';

export type ShellWithQuickInput = Shell & { quick_input?: boolean };

type SpeechWorkspaceProps = {
  mode: 'speech_reconstruction' | 'text_to_speech';
  onModeChange: (mode: string) => void;
  engineId: string;
  onEngineChange: (engineId: string) => void;
  shell: ShellWithQuickInput;
  onShellPatch: (patch: Partial<ShellWithQuickInput>) => Promise<void>;
  onError: (message: string) => void;
  route: { output: string; host_api: string };
  onRouteChange: (route: { output: string; host_api: string }) => void;
  audioDevices: AudioDevices | null;
  audioDeviceError: string;
  audioDeviceBusy: boolean;
  onReloadAudioDevices: () => Promise<void>;
  settingsOnly?: boolean;
  quickOnly?: boolean;
};

const supportedEngines = [
  { id: 'cosyvoice', name: 'CosyVoice', detail: 'CosyVoice2 baseline' },
  { id: 'breeze', name: 'Breeze TTS 2', detail: 'offline candidate' },
];

const activeQueueStatuses = new Set(['current', 'generating', 'buffering', 'playing', 'stopping']);
const pendingQueueStatuses = new Set(['queued', 'pending', 'ready']);
const terminalQueueStatuses = new Set(['completed', 'failed', 'cancelled', 'rejected']);

function stateLabel(state: SpeechState): string {
  return state;
}

function queueLabel(item: SpeechQueueItem): string {
  return item.text.length > 70 ? `${item.text.slice(0, 70)}…` : item.text;
}

function isCompletedPlayback(entry: SpeechSnapshot['transcript'][number]): boolean {
  return entry.source_type === 'self' && entry.provider === 'manual_text' && entry.speech_status === 'completed';
}

function snapshotQueue(snapshot: SpeechSnapshot) {
  const currentById = snapshot.current_request_id
    ? snapshot.queue.find((item) => item.id === snapshot.current_request_id) ?? null
    : null;
  // current_request_id is authoritative for BUFFERING/READY, where the item
  // can still report status=ready while the backend is actively processing it.
  const current = currentById ?? snapshot.queue.find((item) => activeQueueStatuses.has(item.status)) ?? null;
  const pending = snapshot.queue.filter((item) => item.id !== current?.id && (pendingQueueStatuses.has(item.status) || !terminalQueueStatuses.has(item.status)));
  const history = snapshot.queue.filter((item) => item.id !== current?.id && !pending.some((pendingItem) => pendingItem.id === item.id));
  return { current, pending, history };
}

function actionFailure(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function readSessionValue<T>(key: string, fallback: T): T {
  try {
    const value = window.sessionStorage.getItem(`aethertune:speech:${key}`);
    return value === null ? fallback : JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

function writeSessionValue<T>(key: string, value: T): void {
  try {
    window.sessionStorage.setItem(`aethertune:speech:${key}`, JSON.stringify(value));
  } catch {
    // Native WebView storage may be unavailable in a restricted preview; UI state still works in memory.
  }
}

function SpeechStateBadge({ state }: { state: SpeechState }) {
  return <span className={`speech-state speech-state-${state.toLowerCase()}`} data-testid="speech-state">{stateLabel(state)}</span>;
}

function VoiceProfileSelect({
  profiles,
  profileId,
  engineId,
  onChange,
}: {
  profiles: VoiceProfile[];
  profileId: string;
  engineId: string;
  onChange: (id: string) => void;
}) {
  const selected = profiles.find((profile) => profile.id === profileId) ?? profiles[0];
  const reference = selected?.references?.[engineId];
  const referenceAudio = reference?.audio_path || selected?.reference_audio;
  const referenceText = reference?.text_path || selected?.reference_text_file;
  const profileStatus = selected?.status || selected?.metadata?.review_status || 'WAITING';
  const referenceStatus = reference?.metadata_status;
  return <div className="speech-voice-field">
    <label>Voice profile
      <select aria-label="Voice profile" value={selected?.id ?? ''} onChange={(event) => onChange(event.target.value)} disabled={profiles.length === 0}>
        {profiles.length === 0 && <option value="">尚未讀取 profiles</option>}
        {profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
      </select>
    </label>
    {selected && <div className="profile-meta">
      <span className="draft-badge">{profileStatus}</span>
      <span>{referenceAudio || 'reference audio 尚未提供'}</span>
      <small>{referenceText || 'reference text 尚未提供'}</small>
      {referenceStatus && referenceStatus !== profileStatus && <small>reference metadata: {referenceStatus}</small>}
      {selected.note && <small>{selected.note}</small>}
    </div>}
  </div>;
}

function QueueItemActions({
  item,
  busy,
  onAction,
}: {
  item: SpeechQueueItem;
  busy: boolean;
  onAction: (action: SpeechAction) => void;
}) {
  return <div className="queue-item-actions">
    <button type="button" disabled={busy} onClick={() => onAction({ action: 'speak_now', id: item.id })}>Speak Now</button>
    <button type="button" disabled={busy} onClick={() => onAction({ action: 'move_up', id: item.id })}>Move Up</button>
    <button type="button" disabled={busy} onClick={() => onAction({ action: 'move_down', id: item.id })}>Move Down</button>
    <button type="button" disabled={busy} onClick={() => onAction({ action: 'remove', id: item.id })}>Remove</button>
  </div>;
}

export function SpeechWorkspace({
  mode,
  onModeChange,
  engineId,
  onEngineChange,
  shell,
  onShellPatch,
  onError,
  route,
  onRouteChange,
  audioDevices,
  audioDeviceError,
  audioDeviceBusy,
  onReloadAudioDevices,
  settingsOnly = false,
  quickOnly = false,
}: SpeechWorkspaceProps) {
  const [snapshot, setSnapshot] = useState<SpeechSnapshot>(defaultSpeechSnapshot);
  const [inputSource, setInputSource] = useState<SpeechInputSource>('manual_text');
  const [profileId, setProfileId] = useState(() => readSessionValue('profile-id', defaultSpeechSnapshot.profiles[0]?.id ?? ''));
  const [text, setText] = useState(() => readSessionValue('composer', ''));
  const [settings, setSettings] = useState<SpeechSettings>(defaultSpeechSnapshot.settings);
  const [actionBusy, setActionBusy] = useState(false);
  const [localError, setLocalError] = useState('');
  const [localNotice, setLocalNotice] = useState('');
  const composing = useRef(false);
  const mounted = useRef(true);

  useEffect(() => writeSessionValue('input-source', inputSource), [inputSource]);
  useEffect(() => writeSessionValue('profile-id', profileId), [profileId]);
  useEffect(() => writeSessionValue('composer', text), [text]);

  const refresh = useCallback(async () => {
    try {
      const next = await getSpeechStatus();
      if (!mounted.current) return;
      setSnapshot(next);
      setSettings(next.settings);
      if (next.profiles.length && !next.profiles.some((profile) => profile.id === profileId)) setProfileId(next.profiles[0].id);
    } catch (error) {
      if (mounted.current) setLocalError(`Speech status WAITING：${actionFailure(error)}`);
    }
  }, [profileId]);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    let disposed = false;
    let unsubscribe: (() => void) | undefined;
    void subscribeSpeech((next) => {
      if (!disposed) {
        setSnapshot(next);
        setSettings(next.settings);
        if (next.profiles.length && !next.profiles.some((profile) => profile.id === profileId)) setProfileId(next.profiles[0].id);
      }
    }).then((cleanup) => {
      if (disposed) cleanup();
      else unsubscribe = cleanup;
    }).catch((error) => {
      if (!disposed) setLocalError(`speech-event WAITING：${actionFailure(error)}`);
    });
    const timer = window.setInterval(() => void refresh(), native ? 1000 : 5000);
    return () => {
      disposed = true;
      mounted.current = false;
      window.clearInterval(timer);
      unsubscribe?.();
    };
  }, [profileId, refresh]);

  const profiles = useMemo(() => snapshot.profiles.filter((profile) => !profile.engines?.length || profile.engines.includes(engineId)), [engineId, snapshot.profiles]);
  const selectedProfile = profiles.find((profile) => profile.id === profileId) ?? profiles[0];
  const { current, pending, history } = useMemo(() => snapshotQueue(snapshot), [snapshot]);
  const activeQueueCount = (current ? 1 : 0) + pending.length;
  const completedTranscript = useMemo(() => snapshot.transcript.filter(isCompletedPlayback), [snapshot.transcript]);
  const ttsEngine = supportedEngines.find((engine) => engine.id === engineId) ?? supportedEngines[0];
  const profileIsDraft = !selectedProfile || (selectedProfile.status ?? 'draft').toLowerCase() !== 'ready';
  const isMicInput = inputSource === 'microphone';
  const outputIndex = (audioDevices?.outputs ?? []).findIndex((device) => device.selectable && device.name === route.output && device.host_api === route.host_api);
  const routeReady = outputIndex >= 0;
  const routeIsVirtual = /CABLE|Voicemeeter/i.test(route.output);
  const generationStart = current?.metrics?.generation_started_at;
  const generationSeconds = current?.status === 'generating' && typeof generationStart === 'string'
    ? Math.max(0, Math.floor((Date.now() - Date.parse(generationStart)) / 1000))
    : null;
  const inputStatus = inputSource === 'microphone'
    ? `Mic ${snapshot.capabilities.microphone === 'implemented' && snapshot.mic_enabled ? 'ON' : 'WAITING'}`
    : inputSource === 'manual_text' ? 'Manual text implemented' : 'PLANNED';

  const runAction = useCallback(async (action: SpeechAction, enqueue?: boolean): Promise<boolean> => {
    if (!native) {
      const message = '瀏覽器預覽已停用 TTS send；可編輯 composer，但請在 Tauri Desktop 送出。';
      setLocalError(message);
      onError(message);
      return false;
    }
    setActionBusy(true);
    setLocalError('');
    setLocalNotice('');
    try {
      const acknowledgement = await sendSpeechAction(action, enqueue);
      if (acknowledgement.snapshot) setSnapshot((previous) => normalizeSpeechSnapshot({ ...previous, ...acknowledgement.snapshot }));
      await refresh();
      return true;
    } catch (error) {
      const message = actionFailure(error);
      setLocalError(message);
      onError(message);
      return false;
    } finally {
      if (mounted.current) setActionBusy(false);
    }
  }, [onError, refresh]);

  const submit = useCallback(async (enqueue: boolean) => {
    const trimmed = text.trim();
    if (!trimmed) {
      setLocalError('請先輸入要說出的文字。');
      return false;
    }
    if (!selectedProfile) {
      setLocalError('Voice profile 尚未讀取；目前不能建立 submit request。');
      return false;
    }
    if (!routeReady) {
      setLocalError('請先從下拉選單選擇目前可用的輸出裝置。');
      return false;
    }
    const accepted = await runAction({
      action: 'submit',
      request: {
        text: trimmed,
        engine_id: ttsEngine.id,
        voice_profile_id: selectedProfile.id,
        source: 'manual',
        metadata: {
          input_source: inputSource,
          route: {
            output: route.output,
            host_api: route.host_api,
            rack_profile_id: 'seed-vc-neutral',
            route_profile_id: 'seed-vc-virtual-route',
          },
        },
      },
    }, enqueue);
    if (accepted) {
      setText('');
      setLocalNotice(`已加入 Speech Queue；${ttsEngine.name} 會先產生完整 WAV，生成中不會立即出聲。`);
      if (quickOnly) await onShellPatch({ quick_input: false });
    }
    return accepted;
  }, [inputSource, onShellPatch, quickOnly, route, routeReady, runAction, selectedProfile, text, ttsEngine.id, ttsEngine.name]);

  const handleComposerKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey || !settings.enter_to_send || composing.current || event.nativeEvent.isComposing) return;
    event.preventDefault();
    // Enter follows the configured interrupt policy; Add to Queue is the explicit queued action.
    void submit(false);
  };

  const handleSettings = (patch: Partial<SpeechSettings>) => {
    const next = { ...settings, ...patch };
    setSettings(next);
    void runAction({ action: 'settings', settings: next });
  };

  const handleFavorite = (phrase: string) => {
    const pinned = !snapshot.favorites.includes(phrase);
    void runAction({ action: 'favorite', text: phrase, pinned });
  };

  const settingsPanel = <section className="panel speech-settings">
    <div className="speech-panel-title"><h2>Speech settings <span>native persisted</span></h2></div>
    <label>Interrupt policy<select aria-label="Interrupt policy" value={settings.interrupt_policy} disabled={!native || actionBusy} onChange={(event) => handleSettings({ interrupt_policy: event.target.value as InterruptPolicy })}><option value="queue">queue</option><option value="interrupt_current">interrupt_current</option><option value="reject_new">reject_new</option></select></label>
    <label className="check"><input aria-label="Enter to send" type="checkbox" checked={settings.enter_to_send} disabled={!native || actionBusy} onChange={(event) => handleSettings({ enter_to_send: event.target.checked })}/>Enter to send</label>
    <p className="hint">{native ? 'Settings are persisted by speech_action.' : '瀏覽器預覽：native settings disabled。'}</p>
  </section>;

  if (settingsOnly) return <div className="speech-settings-page"><span className="eyebrow">TEXT → VOICE</span><h1>Speech settings</h1>{settingsPanel}</div>;

  const outputSelector = <div className="composer-output">
    <label>輸出裝置<select aria-label="TTS Output" value={outputIndex < 0 ? '' : String(outputIndex)} disabled={!native || !audioDevices || audioDeviceBusy} onChange={(event) => { const device = audioDevices?.outputs[Number(event.target.value)]; if (device?.selectable) onRouteChange({ output: device.name, host_api: device.host_api }); }}><option value="">{audioDeviceBusy ? '正在讀取裝置…' : '請選擇播放裝置'}</option>{audioDevices?.outputs.map((device, index) => <option key={`${device.host_api}-${device.name}-${index}`} value={index} disabled={!device.selectable}>{device.name} · {device.host_api}{device.is_default ? ' · 系統預設' : ''}{!device.selectable ? ' · 名稱重複' : ''}</option>)}</select></label>
    <button type="button" className="text-button" disabled={!native || audioDeviceBusy} onClick={() => void onReloadAudioDevices()}>重新掃描裝置</button>
  </div>;

  const composer = <section className="panel speech-composer">
    <div className="speech-panel-title"><h2>{quickOnly ? 'Quick input' : 'Manual composer'} <span>{text.length} characters</span></h2><span className="speech-input-status">{inputStatus}</span></div>
    <textarea
      aria-label={quickOnly ? 'Compact quick input' : 'Speech composer'}
      value={text}
      placeholder="輸入文字，Enter 送出；Shift+Enter 換行"
      onChange={(event) => setText(event.target.value)}
      onKeyDown={handleComposerKeyDown}
      onCompositionStart={() => { composing.current = true; }}
      onCompositionEnd={() => { composing.current = false; }}
      rows={quickOnly ? 2 : 5}
    />
    {!quickOnly && outputSelector}
    {audioDeviceError && <p role="alert" className="error">裝置清單讀取失敗：{audioDeviceError}</p>}
    <div className="composer-footer"><span className="hint">{current?.status === 'generating' ? `正在生成完整 WAV${generationSeconds === null ? '' : ` · 已等待 ${generationSeconds} 秒`}；完成後才開始播放。` : routeReady ? (routeIsVirtual ? `輸出：${route.output}（虛擬線路；喇叭不會直接出聲）` : `輸出：${route.output}（${route.host_api}）`) : '請先選擇輸出裝置。'}</span><span className="speech-route-label">{current?.status === 'generating' ? 'GENERATING' : 'AUDIO WAITING'}</span></div>
    <div className="composer-actions">
      <button type="button" className="start" disabled={!native || !routeReady || !text.trim() || actionBusy} onClick={() => void submit(false)}>Speak</button>
      {!quickOnly && <button type="button" disabled={!native || !routeReady || !text.trim() || actionBusy} onClick={() => void submit(true)}>Add to Queue</button>}
      {!quickOnly && <button type="button" disabled={!text} onClick={() => setText('')}>Clear</button>}
    </div>
    {!native && <p className="preview-note">瀏覽器預覽：editor 可用，send disabled；不會假造 TTS accepted。</p>}
    {localNotice && <p role="status" className="hint">{localNotice}</p>}
  </section>;

  if (quickOnly) return <section className="speech-quick-popup" data-testid="speech-quick-popup">
    <div className="speech-quick-header"><strong>Text → Voice</strong><button type="button" aria-label="Close quick input" onClick={() => void onShellPatch({ quick_input: false })}>×</button></div>
    {composer}
    {(localError || (snapshot.state === 'ERROR' && snapshot.queue[0]?.error)) && <p role="alert" className="error speech-error">{localError || snapshot.queue[0]?.error}</p>}
  </section>;

  return <div className="speech-workspace" data-speech-mode={mode}>
    <div className="headline speech-headline"><div><span className="eyebrow">{mode === 'speech_reconstruction' ? 'SPEECH RECONSTRUCTION' : 'TEXT → VOICE'}</span><h1>{mode === 'speech_reconstruction' ? '重新合成一段聲音。' : '讓文字成為聲音。'}</h1></div><div className="speech-state-stack"><SpeechStateBadge state={snapshot.state}/><span className="audio-waiting">AUDIO WAITING</span></div></div>
      <div className="speech-layout">
      <div className="speech-main-column">
        <section className="panel speech-controls">
          <div className="speech-panel-title"><h2>Voice controls <span>TTS backend</span></h2><span className="classification">WAITING</span></div>
          <div className="speech-control-grid">
            <label>Mode<select aria-label="Mode" value={mode} onChange={(event) => onModeChange(event.target.value)}><option value="speech_reconstruction">Speech Reconstruction</option><option value="text_to_speech">Text → Voice</option><option value="streaming_vc">Streaming VC</option></select></label>
            <label>Engine<select aria-label="Engine" value={ttsEngine.id} onChange={(event) => onEngineChange(event.target.value)}>{supportedEngines.map((engine) => <option key={engine.id} value={engine.id}>{engine.name}</option>)}</select></label>
            <label>文字來源<select aria-label="Input" value={inputSource} onChange={(event) => setInputSource(event.target.value as SpeechInputSource)}><option value="manual_text">手動輸入文字</option><option value="microphone" disabled>麥克風轉文字 · WAITING</option><option value="agent_reply" disabled>Agent Reply · PLANNED</option></select></label>
            <VoiceProfileSelect profiles={profiles} profileId={profileId} engineId={ttsEngine.id} onChange={setProfileId}/>
          </div>
          <div className="speech-engine-notes"><span>{ttsEngine.detail}</span><span className="planned-badge">CosyVoice3 · PLANNED</span></div>
          <div className="speech-capabilities"><span>Mic {snapshot.capabilities.microphone === 'implemented' && snapshot.mic_enabled ? 'ON' : 'WAITING'}</span><span>Manual text {snapshot.capabilities.manual_text}</span><span>agent_reply {snapshot.capabilities.agent_reply}</span></div>
          <p className="hint">{snapshot.profiles_pending ? 'Voice Library 尚未建立；目前沿用 backend reference catalogue，尚未讀取正式 speech_status profiles。' : 'Voice profiles 由 speech_status snapshot 提供。'}</p>
          {profileIsDraft && <p className="draft-note">Draft profile：reference audio／text 尚未完成正式核對；不代表 active 或 ready。</p>}
          <p className="hint">{isMicInput ? 'microphone real STT：WAITING。manual composer 不受 Mic OFF gate 影響。' : 'manual_text provider 可直接送入 SpeechQueue。'}</p>
          <div className="tts-legacy-start"><button type="button" disabled aria-label="▶ START">▶ START</button><span>TTS 使用 Speak／Queue；VC runner START 保持 disabled。</span></div>
        </section>
        {composer}
        {(localError || (snapshot.state === 'ERROR' && snapshot.queue[0]?.error)) && <p role="alert" className="error speech-error">{localError || snapshot.queue[0]?.error}</p>}
      </div>
      <aside className="speech-side-column">
        <section className="panel speech-queue">
          <div className="speech-panel-title"><h2>Speech Queue <span>{activeQueueCount} active · {history.length} history</span></h2><button type="button" disabled={!native || actionBusy || activeQueueCount === 0} onClick={() => void runAction({ action: 'clear_queue' })}>Clear Queue</button></div>
          {current ? <div className="queue-current"><div className="queue-item-heading"><span className="queue-status">CURRENT · {current.status}{generationSeconds === null ? '' : ` · ${generationSeconds} 秒`}</span><button type="button" disabled={!native || actionBusy} onClick={() => void runAction({ action: 'stop_speaking' })}>Stop Speaking</button></div><p>{current.text}</p><small>{current.engine_id} · {current.voice_profile_id} · {current.route_snapshot?.output ?? '未記錄輸出裝置'}</small>{current.status === 'generating' && <p className="hint">正在載入模型並產生完整語音；播放尚未開始。請勿重複送出。</p>}</div> : <div className="queue-empty-action"><p className="empty-state">No current speech. TTS audio remains WAITING until backend evidence arrives.</p><button type="button" disabled>Stop Speaking</button></div>}
          <div className="queue-pending">{pending.map((item) => <div className="queue-item" key={item.id}><div><span className="queue-status">PENDING · {item.status}</span><p>{queueLabel(item)}</p></div><QueueItemActions item={item} busy={!native || actionBusy} onAction={(action) => void runAction(action)}/></div>)}</div>
          {history.length > 0 && <details className="queue-history" open><summary>Queue history ({history.length})</summary>{history.map((item) => <div className="queue-history-row" key={item.id}><span>{item.status}</span><span>{queueLabel(item)}</span>{item.error && <small>{item.error}</small>}</div>)}</details>}
        </section>
        <section className="panel speech-phrases">
          <div className="speech-panel-title"><h2>Recent / Favorites <span>backend snapshot</span></h2></div>
          <div className="phrase-list">{snapshot.recent_phrases.map((phrase) => <div className="phrase-row" key={phrase}><button type="button" className="phrase-button" onClick={() => setText(phrase)}>{phrase}</button><button type="button" className="pin-button" aria-label={snapshot.favorites.includes(phrase) ? `Unpin ${phrase}` : `Pin ${phrase}`} disabled={!native || actionBusy} onClick={() => handleFavorite(phrase)}>{snapshot.favorites.includes(phrase) ? '★' : '☆'}</button></div>)}</div>
          {snapshot.favorites.length > 0 && <div className="favorite-phrases"><span className="favorite-heading">Favorites</span>{snapshot.favorites.map((phrase) => <div className="phrase-row" key={`favorite-${phrase}`}><button type="button" className="phrase-button" onClick={() => setText(phrase)}>{phrase}</button><button type="button" className="pin-button" aria-label={`Unpin ${phrase}`} disabled={!native || actionBusy} onClick={() => handleFavorite(phrase)}>★</button></div>)}</div>}
        </section>
        {settingsPanel}
        <section className="panel speech-transcript">
          <div className="speech-panel-title"><h2>Transcript <span>completed playback only</span></h2></div>
          {completedTranscript.length === 0 ? <p className="empty-state">尚無 completed playback。failed／cancelled 項目只留在 queue history。</p> : <div className="transcript-list">{completedTranscript.map((entry) => <div className="transcript-row" key={entry.id}><span>ME · manual_text</span><p>{entry.text}</p></div>)}</div>}
        </section>
      </aside>
    </div>
  </div>;
}
