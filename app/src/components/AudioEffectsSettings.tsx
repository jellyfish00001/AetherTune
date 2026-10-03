import { useI18n } from '../services/i18n';
import React from 'react';
import type { VcPostFx, NoiseReduction } from '../services/desktop';
import { audioEffectEngines, defaultAudioEffects } from '../services/audio-effects';
import { HelpIcon } from './HelpIcon';
import { NumberControl } from './NumberControl';

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

export function AudioEffectsSettings({ engine, onEngine, settings, onSettings, saveError, noiseReduction, onNoiseReduction }: {
  engine: string; onEngine: (engine: string) => void;
  settings: VcPostFx; onSettings: (settings: VcPostFx) => void; saveError: string;
  noiseReduction?: NoiseReduction; onNoiseReduction: (settings: NoiseReduction) => void;
}) {
  const { t } = useI18n();
  const name = audioEffectEngines.find((item) => item.id === engine)?.name ?? engine;
  return <section className="panel audio-effects-settings rvc-controls">
    <h1 className="field-caption" aria-label={t('音效設定')}>{t("音效設定")}<HelpIcon label={t('音效設定')} help="help.effects"/></h1>
    <label>{t("設定項目")}<select data-testid="control:音效引擎" aria-label={t("音效引擎")} value={engine} onChange={(event) => onEngine(event.target.value)}>{audioEffectEngines.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    {noiseReduction && <div className="input-noise-settings">
      <h2 className="field-caption">{t('noise.title')}<HelpIcon label={t('noise.title')} help="help.noise"/></h2>
      <label className="check"><input data-testid="control:啟用輸入降噪" aria-label={t('noise.enabled')} type="checkbox" checked={noiseReduction.enabled} onChange={(event) => onNoiseReduction({ ...noiseReduction, enabled: event.target.checked })}/>{t('noise.enabled')}</label>
      <label><span className="field-caption">{t('noise.strength')}<HelpIcon label={t('noise.strength')} help="help.noise.strength"/></span><NumberControl label={t('noise.strength')} testId="control:降噪強度" value={noiseReduction.strength_db} min={0} max={24} step={1} onChange={(number) => onNoiseReduction({ ...noiseReduction, strength_db: number })}/></label>
    </div>}
    <label className="check"><input data-testid="control:啟用音效" aria-label={t("啟用音效")} type="checkbox" checked={settings.enabled} onChange={(event) => onSettings({ ...settings, enabled: event.target.checked })}/>{t("啟用音效")}</label>
    <div className="device-fields">{fields.map(({ key, label, aria, min, max, step }) => <label key={key}><span className="field-caption">{t(label)}<HelpIcon label={t(label)} help={`help.fx.${key}`}/></span><NumberControl label={t(aria)} testId={`control:${aria}`} value={settings[key]} min={min} max={max} step={step} onChange={(number) => onSettings({ ...settings, [key]: number })}/></label>)}</div>
    <p className="hint">{t('effects.apply')}</p>
    <button type="button" className="text-button" onClick={() => onSettings({ ...defaultAudioEffects })}>{t("重設此項目音效")}</button>
    <p role={saveError ? 'alert' : 'status'} className={saveError ? 'error' : 'hint'}>{t(saveError || '音效紀錄已自動儲存。')}</p>
    <details className="audio-troubleshooting"><summary>{t('audio.troubleshoot')}</summary>{['gaps', 'tremble', 'robot', 'pitch', 'noise'].map((symptom) => <div key={symptom}><h3>{t(`symptom.${symptom}`)}</h3><p>{t(`help.symptom.${symptom}`)}</p></div>)}</details>
  </section>;
}
