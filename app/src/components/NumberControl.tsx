import React, { useEffect, useState } from 'react';
import { useI18n } from '../services/i18n';

export function NumberControl({ value, onChange, min, max, step = 1, label, testId, disabled = false }: {
  value: number | string; onChange: (value: number) => void; min: number; max: number; step?: number; label: string; testId: string; disabled?: boolean;
}) {
  const { t } = useI18n();
  const [draft, setDraft] = useState(String(value));
  useEffect(() => setDraft(String(value)), [value]);
  const normalized = (text: string) => {
    const number = text.trim() === '' ? NaN : Number(text);
    const fallback = Number(value);
    const finite = Number.isFinite(number) ? number : Number.isFinite(fallback) ? fallback : min;
    return Number(Math.min(max, Math.max(min, min + Math.round((finite - min) / step) * step)).toFixed(8));
  };
  const commit = (number = normalized(draft)) => { setDraft(String(number)); onChange(number); };
  const increment = (direction: number) => commit(normalized(String(normalized(draft) + direction * step)));
  return <span className="number-control">
    <input type="number" aria-label={label} data-testid={testId} min={min} max={max} step={step} disabled={disabled} value={draft} onChange={(event) => setDraft(event.target.value)} onBlur={() => commit()} onKeyDown={(event) => {
      if (event.key === 'ArrowUp' || event.key === 'ArrowDown') { event.preventDefault(); increment(event.key === 'ArrowUp' ? 1 : -1); }
      if (event.key === 'Enter') { event.preventDefault(); commit(); }
    }}/>
    <span className="number-buttons"><button type="button" aria-label={t('number.increase', { label })} disabled={disabled || normalized(draft) >= max} onMouseDown={(event) => event.preventDefault()} onClick={() => increment(1)}>▴</button><button type="button" aria-label={t('number.decrease', { label })} disabled={disabled || normalized(draft) <= min} onMouseDown={(event) => event.preventDefault()} onClick={() => increment(-1)}>▾</button></span>
  </span>;
}
