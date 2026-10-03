import React from 'react';
import { useI18n } from '../services/i18n';
import type { Manifest, EngineParameter } from '../services/desktop';
import { HelpIcon } from './HelpIcon';
import { NumberControl } from './NumberControl';

export function EngineParameters({ manifest, parameters, onParameters, locked }: {
  manifest: Manifest; parameters: Record<string, string | number>; onParameters: (value: Record<string, string | number>) => void; locked: boolean;
}) {
  const { t } = useI18n();
  const labels: Record<string, string> = { microphone: '麥克風即時變聲', file: '來源 WAV 測試', fcpe: 'FCPE', rmvpe: 'RMVPE' };
  const field = (p: EngineParameter) => {
    const label = t(p.label), prefix = manifest.id === 'rvc' ? 'RVC' : `VC ${manifest.id}`;
    return <label key={p.name}><span className="field-caption">{label}<HelpIcon label={label} help={`help.${manifest.id}.${p.name}`}/></span>
      {p.type === 'select' ? <select data-testid={`control:${prefix} ${p.name}`} aria-label={`${prefix} ${label}`} disabled={locked} value={parameters[p.name]} onChange={(event) => onParameters({ ...parameters, [p.name]: event.target.value })}>{p.options?.map((option) => <option key={option} value={option}>{t(labels[option] ?? option)}</option>)}</select>
        : <NumberControl label={`${prefix} ${label}`} testId={`control:${prefix} ${p.name}`} disabled={locked} min={p.min ?? 0} max={p.max ?? 100} step={p.step} value={parameters[p.name] ?? p.default as number} onChange={(number) => onParameters({ ...parameters, [p.name]: number })}/>}
    </label>;
  };
  return <div className="rvc-controls engine-parameters"><div className="device-fields">{manifest.parameters.filter((p) => p.level === 'basic').map(field)}</div>
    {manifest.parameters.some((p) => p.level === 'advanced') && <details key={manifest.id}><summary>{t(manifest.id === 'rvc' ? 'RVC 進階參數' : 'parameters.advanced')}</summary><div className="device-fields">{manifest.parameters.filter((p) => p.level === 'advanced').map(field)}</div></details>}
  </div>;
}
