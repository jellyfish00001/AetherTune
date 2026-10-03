import { command, native, subscribe, type VcPostFx, type RuntimeProgress } from './desktop';
import referenceFemale from '../../../contracts/voices/reference-female.json';
import referenceMale from '../../../contracts/voices/reference-male.json';
import officialCosyVoiceSample from '../../../contracts/voices/official-cosyvoice-sample.json';
import referenceMandarinFemale from '../../../contracts/voices/reference-mandarin-female.json';

export type SpeechState =
  | 'IDLE'
  | 'QUEUED'
  | 'GENERATING'
  | 'BUFFERING'
  | 'PLAYING'
  | 'STOPPING'
  | 'ERROR';

export type SpeechInputSource = 'microphone' | 'manual_text' | 'agent_reply';
export type InterruptPolicy = 'queue' | 'interrupt_current' | 'reject_new';

export type SpeechQueueItem = {
  id: string;
  session_id: string;
  source: 'manual' | 'microphone' | 'agent_reply' | string;
  text: string;
  engine_id: string;
  voice_profile_id: string;
  created_at: string;
  status: string;
  priority: number;
  metrics?: Record<string, unknown>;
  route_snapshot?: { output: string; host_api: string };
  error?: string;
};

export type SpeechTranscript = {
  id: string;
  session_id?: string;
  text: string;
  source_type: 'self' | string;
  provider: 'manual_text' | string;
  speech_status: string;
  created_at?: string;
  completed_at?: string;
  [key: string]: unknown;
};

export type VoiceProfile = {
  id: string;
  name: string;
  reference_audio: string;
  reference_text_file: string;
  engines?: string[];
  status?: string;
  source?: string;
  note?: string;
  references?: Record<string, VoiceReference>;
  metadata?: VoiceProfileMetadata;
  official_cosyvoice_sample?: VoiceReference;
  profile_path?: string;
};

export type VoiceReference = {
  audio_path: string;
  text_path: string;
  metadata_status?: string;
  notes?: string;
};

export type VoiceProfileMetadata = {
  review_status?: string;
  manual_review_required?: boolean;
  source?: string;
  notes?: string;
};

export type SpeechSettings = {
  interrupt_policy: InterruptPolicy;
  enter_to_send: boolean;
};

export type AudioDevice = {
  name: string;
  host_api: string;
  channels: number;
  is_default: boolean;
  selectable: boolean;
};

export type AudioDevices = {
  inputs: AudioDevice[];
  outputs: AudioDevice[];
};

export type SpeechRoute = {
  output: string;
  host_api: string;
  monitor?: { enabled: boolean; output: string; host_api: string };
};

export type OutputDeviceChoice = { device: AudioDevice; index: number; label: string; isDefault: boolean };

export function outputDeviceChoices(
  outputs: AudioDevice[],
  route?: { output: string; host_api: string },
  showAll = false,
): OutputDeviceChoice[] {
  const choices = outputs.map((device, index) => ({ device, index, label: device.name, isDefault: device.is_default }));
  if (showAll) return choices;
  const selected = choices.find(({ device }) => device.selectable && device.name === route?.output && device.host_api === route?.host_api);
  const usable = choices.filter(({ device }) => device.selectable);
  const hasStandardApi = usable.some(({ device }) => device.host_api !== 'Windows WDM-KS');
  const fullNames = [...new Set(usable.filter(({ device }) => ['Windows DirectSound', 'Windows WASAPI'].includes(device.host_api)).map(({ device }) => device.name.trim()))];
  const groups = new Map<string, OutputDeviceChoice[]>();
  for (const choice of usable) {
    const { device } = choice;
    // MME 會截短名稱；只有唯一符合完整名稱時才合併，避免把不同裝置猜成同一個。
    const prefix = device.name.trim();
    const matches = device.host_api === 'MME' ? fullNames.filter((name) => name.startsWith(prefix)) : [];
    const name = matches.length === 1 ? matches[0] : prefix;
    const alias = /^(Microsoft (Sound Mapper|音效對應表) - Output|Primary Sound Driver|主要音效驅動程式)$/i.test(name);
    const extraChannel = /^(Voicemeeter In \d+\b|CABLE In 16\s*ch\b)/i.test(name);
    if (choice !== selected && (alias || extraChannel || (hasStandardApi && device.host_api === 'Windows WDM-KS'))) continue;
    const group = groups.get(name) ?? [];
    group.push({ ...choice, label: name });
    groups.set(name, group);
  }
  const apiRank = (device: AudioDevice) => ['Windows DirectSound', 'MME', 'Windows WASAPI'].indexOf(device.host_api);
  return [...groups.values()].map((group) => {
    // 清單精簡不改播放身分：保留目前選中的 exact name + host_api，再優先系統預設。
    const choice = group.find((item) => item.index === selected?.index)
      ?? group.find((item) => item.isDefault)
      ?? [...group].sort((a, b) => (apiRank(a.device) < 0 ? 99 : apiRank(a.device)) - (apiRank(b.device) < 0 ? 99 : apiRank(b.device)))[0];
    return { ...choice, isDefault: group.some((item) => item.isDefault) };
  });
}

export type SpeechCapabilities = {
  microphone: 'WAITING' | string;
  manual_text: 'implemented' | string;
  agent_reply: 'PLANNED' | string;
};

export type SpeechSnapshot = {
  progress?: RuntimeProgress | null;
  session_id: string;
  state: SpeechState;
  current_request_id: string | null;
  queue: SpeechQueueItem[];
  transcript: SpeechTranscript[];
  profiles: VoiceProfile[];
  settings: SpeechSettings;
  recent_phrases: string[];
  favorites: string[];
  mic_enabled: boolean;
  capabilities: SpeechCapabilities;
  /** UI-only provenance flags; they never claim that audio is ready. */
  profiles_source?: 'speech_status' | 'backend_reference_catalogue';
  profiles_pending?: boolean;
  audio_status?: 'WAITING';
};

export type SpeechSubmitRequest = {
  text: string;
  engine_id: string;
  voice_profile_id: string;
  source: 'manual';
  metadata: {
    input_source: SpeechInputSource;
    postfx: VcPostFx;
    route: SpeechRoute & {
      rack_profile_id: string;
      route_profile_id: string;
    };
  };
};

export type SpeechAction =
  | { action: 'audio_devices' }
  | { action: 'submit'; request: SpeechSubmitRequest; enqueue?: boolean }
  | { action: 'stop_speaking' }
  | { action: 'clear_queue' }
  | { action: 'remove'; id: string }
  | { action: 'move_up'; id: string }
  | { action: 'move_down'; id: string }
  | { action: 'speak_now'; id: string }
  | { action: 'settings'; settings: SpeechSettings }
  | { action: 'favorite'; text: string; pinned: boolean };

export type SpeechActionAck = {
  accepted: boolean;
  message?: string;
  error?: unknown;
  result?: unknown;
  snapshot?: Partial<SpeechSnapshot>;
  [key: string]: unknown;
};

/**
 * 這是現有 backend reference catalogue 的 UI fallback，不是新增 Voice Library。
 * 所有項目都標示 draft/candidate，直到 Rust speech_status 提供正式 snapshot。
 */
type ContractVoiceProfile = {
  id: string;
  name: string;
  engines: string[];
  status?: string;
  metadata?: VoiceProfileMetadata;
  references?: Record<string, VoiceReference>;
  official_cosyvoice_sample?: VoiceReference;
  profile_path?: string;
};

function fromContractProfile(profile: ContractVoiceProfile): VoiceProfile {
  const references = profile.references ?? {};
  const primary = references.cosyvoice ?? references.breeze ?? profile.official_cosyvoice_sample;
  return {
    id: profile.id,
    name: profile.name,
    reference_audio: primary?.audio_path ?? '',
    reference_text_file: primary?.text_path ?? '',
    engines: profile.engines,
    status: profile.status ?? profile.metadata?.review_status ?? 'WAITING',
    source: profile.metadata?.source ?? 'contracts/voices',
    note: profile.metadata?.notes,
    references,
    metadata: profile.metadata,
    official_cosyvoice_sample: profile.official_cosyvoice_sample,
    profile_path: profile.profile_path,
  };
}

// 直接匯入 contracts/voices，避免預覽 registry 與 backend profile IDs 分叉。
export const backendReferenceCatalogue: VoiceProfile[] = [
  fromContractProfile(officialCosyVoiceSample as ContractVoiceProfile),
  fromContractProfile(referenceMandarinFemale as ContractVoiceProfile),
  fromContractProfile(referenceFemale as ContractVoiceProfile),
  fromContractProfile(referenceMale as ContractVoiceProfile),
].map((profile) => ({ ...profile, source: 'backend_reference_catalogue' }));

export const defaultSpeechSnapshot: SpeechSnapshot = {
  session_id: 'speech-preview-session',
  state: 'IDLE',
  current_request_id: null,
  queue: [],
  transcript: [],
  profiles: backendReferenceCatalogue,
  settings: { interrupt_policy: 'queue', enter_to_send: true },
  recent_phrases: [],
  favorites: [],
  mic_enabled: false,
  capabilities: {
    microphone: 'WAITING',
    manual_text: 'implemented',
    agent_reply: 'PLANNED',
  },
  profiles_source: 'backend_reference_catalogue',
  profiles_pending: true,
  audio_status: 'WAITING',
};

const cloneDefaultSnapshot = (): SpeechSnapshot => ({
  ...defaultSpeechSnapshot,
  queue: [],
  transcript: [],
  profiles: backendReferenceCatalogue.map((profile) => ({ ...profile })),
  settings: { ...defaultSpeechSnapshot.settings },
  recent_phrases: [...defaultSpeechSnapshot.recent_phrases],
  favorites: [],
  capabilities: { ...defaultSpeechSnapshot.capabilities },
});

const validStates = new Set<SpeechState>([
  'IDLE',
  'QUEUED',
  'GENERATING',
  'BUFFERING',
  'PLAYING',
  'STOPPING',
  'ERROR',
]);

function asString(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.trim() ? value : fallback;
}

function asBoolean(value: unknown, fallback: boolean): boolean {
  return typeof value === 'boolean' ? value : fallback;
}

function asErrorMessage(value: unknown): string | undefined {
  if (typeof value === 'string') return value;
  if (!value || typeof value !== 'object') return undefined;
  const error = value as { code?: unknown; message?: unknown };
  const message = typeof error.message === 'string' ? error.message : '';
  const code = typeof error.code === 'string' ? error.code : '';
  if (code && message) return `${code}: ${message}`;
  return message || code || JSON.stringify(value);
}

function asVoiceReference(value: unknown): VoiceReference | undefined {
  if (!value || typeof value !== 'object') return undefined;
  const reference = value as Partial<VoiceReference>;
  const audioPath = asString(reference.audio_path, '');
  const textPath = asString(reference.text_path, '');
  if (!audioPath && !textPath) return undefined;
  return {
    audio_path: audioPath,
    text_path: textPath,
    metadata_status: typeof reference.metadata_status === 'string' ? reference.metadata_status : undefined,
    notes: typeof reference.notes === 'string' ? reference.notes : undefined,
  };
}

function normalizeVoiceProfile(value: unknown): VoiceProfile | undefined {
  if (!value || typeof value !== 'object') return undefined;
  const profile = value as Partial<VoiceProfile> & {
    metadata?: VoiceProfileMetadata;
    references?: Record<string, unknown>;
    official_cosyvoice_sample?: unknown;
  };
  const references: Record<string, VoiceReference> = {};
  if (profile.references && typeof profile.references === 'object') {
    for (const [engine, reference] of Object.entries(profile.references)) {
      const normalized = asVoiceReference(reference);
      if (normalized) references[engine] = normalized;
    }
  }
  const official = asVoiceReference(profile.official_cosyvoice_sample);
  const primary = references.cosyvoice ?? references.breeze ?? official;
  const metadata = profile.metadata && typeof profile.metadata === 'object' ? {
    review_status: typeof profile.metadata.review_status === 'string' ? profile.metadata.review_status : undefined,
    manual_review_required: typeof profile.metadata.manual_review_required === 'boolean' ? profile.metadata.manual_review_required : undefined,
    source: typeof profile.metadata.source === 'string' ? profile.metadata.source : undefined,
    notes: typeof profile.metadata.notes === 'string' ? profile.metadata.notes : undefined,
  } : undefined;
  const id = asString(profile.id, 'unregistered-profile');
  return {
    id,
    name: asString(profile.name, 'Unnamed draft profile'),
    reference_audio: asString(profile.reference_audio, primary?.audio_path ?? ''),
    reference_text_file: asString(profile.reference_text_file, primary?.text_path ?? ''),
    engines: Array.isArray(profile.engines) ? profile.engines.filter((engine): engine is string => typeof engine === 'string') : undefined,
    status: asString(profile.status, metadata?.review_status ?? 'WAITING'),
    source: asString(profile.source, metadata?.source ?? 'speech_status'),
    note: typeof profile.note === 'string' ? profile.note : metadata?.notes,
    references: Object.keys(references).length ? references : undefined,
    metadata,
    official_cosyvoice_sample: official,
    profile_path: typeof profile.profile_path === 'string' ? profile.profile_path : undefined,
  };
}

function asSettings(value: unknown): SpeechSettings {
  const settings = value && typeof value === 'object' ? value as Partial<SpeechSettings> : {};
  const policy = settings.interrupt_policy;
  return {
    interrupt_policy: policy === 'interrupt_current' || policy === 'reject_new' ? policy : 'queue',
    enter_to_send: asBoolean(settings.enter_to_send, true),
  };
}

/**
 * Rust 端在 service 尚未完成初始化時可能只回傳部分欄位；UI 仍保留 WAITING 邊界，
 * 並以明確的 draft catalogue 呈現可選 reference，而不是假造 active profile。
 */
export function normalizeSpeechSnapshot(value: unknown): SpeechSnapshot {
  const input = value && typeof value === 'object' ? value as Partial<SpeechSnapshot> : {};
  const rawProfiles = Array.isArray(input.profiles) ? input.profiles : [];
  const profiles = rawProfiles
    .map(normalizeVoiceProfile)
    .filter((profile): profile is VoiceProfile => profile !== undefined);
  const fromSnapshot = profiles.length > 0;
  const base = cloneDefaultSnapshot();
  const state = validStates.has(input.state as SpeechState) ? input.state as SpeechState : base.state;
  const rawCapabilities = input.capabilities && typeof input.capabilities === 'object'
    ? input.capabilities as Partial<SpeechCapabilities>
    : {};
  return {
    session_id: asString(input.session_id, base.session_id),
    state,
    current_request_id: typeof input.current_request_id === 'string' ? input.current_request_id : null,
    progress: input.progress && typeof input.progress.phase === 'string' && Number.isFinite(input.progress.elapsed_seconds) && Number.isFinite(input.progress.last_progress_seconds_ago) && Number.isFinite(Date.parse(input.progress.observed_at)) ? input.progress : null,
    queue: Array.isArray(input.queue) ? input.queue.filter(Boolean).map((item) => {
      const raw = item as SpeechQueueItem & { error?: unknown };
      return { ...raw, error: asErrorMessage(raw.error) } as SpeechQueueItem;
    }) : [],
    transcript: Array.isArray(input.transcript) ? input.transcript.filter(Boolean) as SpeechTranscript[] : [],
    profiles: fromSnapshot ? profiles : base.profiles,
    settings: asSettings(input.settings),
    recent_phrases: Array.isArray(input.recent_phrases) ? input.recent_phrases.filter((phrase): phrase is string => typeof phrase === 'string') : base.recent_phrases,
    favorites: Array.isArray(input.favorites) ? input.favorites.filter((phrase): phrase is string => typeof phrase === 'string') : [],
    mic_enabled: asBoolean(input.mic_enabled, false),
    capabilities: {
      microphone: asString(rawCapabilities.microphone, 'WAITING'),
      manual_text: asString(rawCapabilities.manual_text, 'implemented'),
      agent_reply: asString(rawCapabilities.agent_reply, 'PLANNED'),
    },
    profiles_source: fromSnapshot ? 'speech_status' : 'backend_reference_catalogue',
    profiles_pending: !fromSnapshot,
    audio_status: 'WAITING',
  };
}

export async function getSpeechStatus(): Promise<SpeechSnapshot> {
  if (!native) return cloneDefaultSnapshot();
  return normalizeSpeechSnapshot(await command<unknown>('speech_status'));
}

export async function getAudioDevices(): Promise<AudioDevices> {
  if (!native) return { inputs: [], outputs: [] };
  const acknowledgement = await sendSpeechAction({ action: 'audio_devices' });
  const result = acknowledgement.result as Partial<AudioDevices> | undefined;
  if (!result || !Array.isArray(result.inputs) || !Array.isArray(result.outputs)) {
    throw new Error('Audio device list 回傳格式不正確');
  }
  return { inputs: result.inputs, outputs: result.outputs };
}

/**
 * speech_action 只傳 metadata／狀態命令，不傳 PCM 或音訊 buffer。
 * submit 的 enqueue 旗標放在 action 內，符合 Rust server-command bridge 契約。
 */
export async function sendSpeechAction(action: SpeechAction, enqueue?: boolean): Promise<SpeechActionAck> {
  if (!native) throw new Error('瀏覽器預覽已停用 TTS send；請使用 Tauri Desktop。');
  // Rust bridge 會把整個 action（含 submit 的 enqueue）送進 JSONL service；
  // enqueue 不放在 command 外層，避免 native command 與 stdin schema 分叉。
  const wireAction: SpeechAction = action.action === 'submit' && typeof enqueue === 'boolean'
    ? { ...action, enqueue }
    : action;
  const args: Record<string, unknown> = { action: wireAction };
  const acknowledgement = await command<SpeechActionAck>('speech_action', args);
  if (!acknowledgement || acknowledgement.accepted !== true) {
    throw new Error(asErrorMessage(acknowledgement?.error) ?? acknowledgement?.message ?? 'TTS action rejected');
  }
  return acknowledgement;
}

export async function subscribeSpeech(callback: (snapshot: SpeechSnapshot) => void): Promise<() => void> {
  if (!native) return () => undefined;
  return subscribe<unknown>('speech-event', (value) => {
    // speech-event 同時承載 ack/log；只有 speech_snapshot 才能更新 UI snapshot。
    if (!value || typeof value !== 'object') return;
    const event = value as { type?: unknown; snapshot?: unknown };
    if (event.type === 'speech_snapshot' && event.snapshot) callback(normalizeSpeechSnapshot(event.snapshot));
  });
}
