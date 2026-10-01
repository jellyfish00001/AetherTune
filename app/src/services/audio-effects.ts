import type { VcPostFx } from './desktop';

export const audioEffectsStorageKey = 'aethertune.audio-effects.v1';
export const audioEffectEngines = [
  { id: 'rvc', name: 'RVC' },
  { id: 'meanvc2', name: 'MeanVC2' },
  { id: 'xvc', name: 'X-VC' },
  { id: 'seed-vc', name: 'Seed-VC' },
  { id: 'cosyvoice', name: 'CosyVoice' },
  { id: 'breeze', name: 'Breeze TTS 2' },
];
export const defaultAudioEffects: VcPostFx = {
  enabled: false, wet: 0.3, low_db: 0, mid_db: 0, high_db: 0,
  compressor_threshold_db: -18, compressor_ratio: 3, reverb_mix: 0.12, output_gain_db: 0,
};
export type AudioEffectsRecords = Record<string, VcPostFx>;

export function normalizeAudioEffects(value: unknown): VcPostFx {
  const record = value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown> : {};
  const number = (key: keyof VcPostFx, min: number, max: number): number => {
    const candidate = record[key];
    return typeof candidate === 'number' && Number.isFinite(candidate)
      ? Math.min(max, Math.max(min, candidate)) : defaultAudioEffects[key] as number;
  };
  return {
    enabled: typeof record.enabled === 'boolean' ? record.enabled : false,
    wet: number('wet', 0, 1), low_db: number('low_db', -12, 12),
    mid_db: number('mid_db', -12, 12), high_db: number('high_db', -12, 12),
    compressor_threshold_db: number('compressor_threshold_db', -48, 0),
    compressor_ratio: number('compressor_ratio', 1, 8),
    reverb_mix: number('reverb_mix', 0, 0.5), output_gain_db: number('output_gain_db', -12, 6),
  };
}

export function readAudioEffects(legacyVcEffects?: VcPostFx): AudioEffectsRecords {
  const records = Object.fromEntries(audioEffectEngines.map(({ id }) => [id, { ...defaultAudioEffects }]));
  // 舊版只有一份共用 VC 音效；移轉到預設 RVC，不把啟用狀態複製給其他引擎。
  records.rvc = normalizeAudioEffects(legacyVcEffects);
  try {
    const raw = window.localStorage.getItem(audioEffectsStorageKey);
    if (raw) {
      const saved: unknown = JSON.parse(raw);
      if (saved && typeof saved === 'object' && !Array.isArray(saved)) {
        for (const { id } of audioEffectEngines) {
          records[id] = normalizeAudioEffects((saved as Record<string, unknown>)[id]);
        }
      }
    }
  } catch {
    // JSON 損壞時保留可用預設；寫入失敗由設定畫面明確回報。
  }
  return records;
}
