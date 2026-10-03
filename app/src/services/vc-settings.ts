import { previewManifests, type NoiseReduction } from './desktop';
export const vcEngineIds = ['rvc', 'meanvc2', 'xvc', 'seed-vc'];
export type EngineParametersRecords = Record<string, Record<string, string | number>>;
export const defaultNoiseReduction: NoiseReduction = { enabled: false, strength_db: 12 };
export function normalizeNoiseReduction(value: unknown): NoiseReduction {
  const saved = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  return { enabled: saved.enabled === true, strength_db: typeof saved.strength_db === 'number' && Number.isFinite(saved.strength_db) ? Math.min(24, Math.max(0, saved.strength_db)) : 12 };
}
export function readEngineParameters(saved: unknown, legacy: unknown): EngineParametersRecords {
  const records = saved && typeof saved === 'object' ? saved as Record<string, unknown> : {};
  return Object.fromEntries(vcEngineIds.map((id) => {
    const stored = records[id] ?? (id === 'rvc' ? legacy : undefined);
    const values = stored && typeof stored === 'object' ? stored as Record<string, unknown> : {};
    return [id, Object.fromEntries(previewManifests.find((m) => m.id === id)!.parameters.map((p) => {
      const number = values[p.name];
      const value = p.type === 'select' ? (typeof number === 'string' && p.options?.includes(number) ? number : p.default)
        : typeof number === 'number' && Number.isFinite(number) ? Number(Math.min(p.max!, Math.max(p.min!, p.min! + Math.round((number - p.min!) / p.step!) * p.step!)).toFixed(8)) : p.default;
      return [p.name, value];
    }))];
  })) as EngineParametersRecords;
}
export function readNoiseRecords(saved: unknown): Record<string, NoiseReduction> {
  const values = saved && typeof saved === 'object' ? saved as Record<string, unknown> : {};
  return Object.fromEntries(vcEngineIds.map((id) => [id, normalizeNoiseReduction(values[id])]));
}
export function engineParameterError(engine: string, p: Record<string, string | number>): string {
  if (engine === 'rvc' && Number(p.crossfade) > Number(p.chunk)) return 'parameters.invalid.rvc';
  if (engine === 'seed-vc' && (Number(p.crossfade_length) > Number(p.block_time) || Number(p.extra_time_ce) < Number(p.extra_time))) return 'parameters.invalid.seed';
  if (engine === 'xvc' && (Number(p.current) <= 0 || ['current', 'chunk', 'future'].some((key) => Number(p[key]) % 80 !== 0) || Number(p.smooth) > Number(p.current) || Number(p.current) + Number(p.future) + Number(p.smooth) > Number(p.chunk))) return 'parameters.invalid.xvc';
  return '';
}
