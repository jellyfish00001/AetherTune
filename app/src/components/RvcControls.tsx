import { useI18n } from '../services/i18n';
import React from 'react';
import manifest from '../../../contracts/engines/rvc.json';

export const defaultRvcParameters = Object.fromEntries(manifest.parameters.map((parameter) => [parameter.name, parameter.default])) as Record<string, string | number>;

export function RvcControls({ parameters, onParameters, locked }: {
  parameters: Record<string, string | number>;
  onParameters: (parameters: Record<string, string | number>) => void;
  locked: boolean;
}) {
  const { t } = useI18n();
  const labels: Record<string, string> = { microphone: '麥克風即時變聲', file: '來源 WAV 測試', fcpe: 'FCPE', rmvpe: 'RMVPE' };
  const field = (parameter: typeof manifest.parameters[number]) => <label key={parameter.name}>{t(parameter.label)}
    {parameter.type === 'select' ? <select data-testid={`control:RVC ${parameter.name}`} aria-label={`RVC ${t(parameter.label)}`} disabled={locked} value={parameters[parameter.name]} onChange={(event) => onParameters({ ...parameters, [parameter.name]: event.target.value })}>
      {parameter.options?.map((option) => <option value={option} key={option}>{t(labels[option] ?? option)}</option>)}
    </select> : <input data-testid={`control:RVC ${parameter.name}`} aria-label={`RVC ${t(parameter.label)}`} disabled={locked} type="number" min={parameter.min} max={parameter.max} step={parameter.step} value={parameters[parameter.name]} onChange={(event) => onParameters({ ...parameters, [parameter.name]: event.target.value === '' ? '' : Number(event.target.value) })}/>}
  </label>;
  return <div className="rvc-controls">
    <div className="device-fields">{manifest.parameters.filter((parameter) => parameter.level === 'basic').map(field)}</div>
    <details><summary>{t("RVC 進階參數")}</summary><div className="device-fields">{manifest.parameters.filter((parameter) => parameter.level === 'advanced').map(field)}</div></details>
  </div>;
}
