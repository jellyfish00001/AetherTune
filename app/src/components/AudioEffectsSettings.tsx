import { useI18n } from '../services/i18n';
import React, { useEffect, useState } from 'react';
import type { VcPostFx } from '../services/desktop';
import { audioEffectEngines, defaultAudioEffects } from '../services/audio-effects';

type NumberKey = Exclude<keyof VcPostFx, 'enabled'>;
const fields: { key: NumberKey; label: string; aria: string; min: number; max: number; step: number }[] = [
  { key: 'wet', label: '乾濕混合（0～1）', aria: 'Post-FX wet', min: 0, max: 1, step: 0.01 },
  { key: 'output_gain_db', label: '輸出增益（dB）', aria: 'Post-FX output gain', min: -12, max: 6, step: 0.1 },
  { key: 'low_db', label: '低頻 EQ（dB）', aria: 'Post-FX low', min: -12, max: 12, step: 0.1 },
  { key: 'mid_db', label: '中頻 EQ（dB）', aria: 'Post-FX mid', min: -12, max: 12, step: 0.1 },
  { key: 'high_db', label: '高頻 EQ（dB）', aria: 'Post-FX high', min: -12, max: 12, step: 0.1 },
  { key: 'compressor_threshold_db', label: '壓縮閾值（dB）', aria: 'Post-FX compressor threshold', min: -48, max: 0, step: 1 },
  { key: 'compressor_ratio', label: '壓縮比', aria: 'Post-FX compressor ratio', min: 1, max: 8, step: 0.1 },
  { key: 'reverb_mix', label: '殘響比例', aria: 'Post-FX reverb mix', min: 0, max: 0.5, step: 0.01 },
];

export function AudioEffectsSettings({ engine, onEngine, settings, onSettings, saveError }: {
  engine: string; onEngine: (engine: string) => void;
  settings: VcPostFx; onSettings: (settings: VcPostFx) => void; saveError: string;
}) {
  const { t } = useI18n();
  const [draft, setDraft] = useState<Record<string, string>>({});
  useEffect(() => setDraft(Object.fromEntries(fields.map(({ key }) => [key, String(settings[key])]))), [settings]);
  const name = audioEffectEngines.find((item) => item.id === engine)?.name ?? engine;
  return <section className="panel audio-effects-settings rvc-controls">
    <h1>{t("音效設定")}</h1>
    <label>{t("設定項目")}<select data-testid="control:音效引擎" aria-label={t("音效引擎")} value={engine} onChange={(event) => onEngine(event.target.value)}>{audioEffectEngines.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    <p className="hint">{t('effects.record', { engine: name })}</p>
    <label className="check"><input data-testid="control:啟用音效" aria-label={t("啟用音效")} type="checkbox" checked={settings.enabled} onChange={(event) => onSettings({ ...settings, enabled: event.target.checked })}/>{t("啟用音效")}</label>
    <div className="device-fields">{fields.map(({ key, label, aria, min, max, step }) => <label key={key}>{t(label)}<input data-testid={`control:${aria}`} aria-label={t(aria)} type="number" min={min} max={max} step={step} value={draft[key] ?? String(settings[key])} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} onBlur={(event) => {
      const value = event.target.value.trim() === '' ? NaN : Number(event.target.value);
      // 保留負號／空值等輸入中的文字；離開欄位才校驗、限制範圍並保存。
      const next = Number.isFinite(value) ? Math.min(max, Math.max(min, value)) : settings[key];
      onSettings({ ...settings, [key]: next });
    }}/></label>)}</div>
    <p className="hint">{t("數值離開欄位後自動儲存。變聲於下一次 START 套用；文字發聲於下一次送出套用，已排隊的句子保留原設定。")}</p>
    <p className="hint">{t("乾濕 0 是變聲／生成後的乾聲，1 是音效處理聲。關閉音效完全略過 EQ、壓縮、殘響與增益。")}</p>
    <button type="button" className="text-button" onClick={() => onSettings({ ...defaultAudioEffects })}>{t("重設此項目音效")}</button>
    <p role={saveError ? 'alert' : 'status'} className={saveError ? 'error' : 'hint'}>{t(saveError || '音效紀錄已自動儲存。')}</p>
  </section>;
}
