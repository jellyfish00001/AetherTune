import React, { useEffect, useState } from 'react';
import estimates from '../../../contracts/model-load-estimates.json';
import type { RuntimeProgress } from '../services/desktop';
import { useI18n } from '../services/i18n';
import { HelpIcon } from './HelpIcon';

export function LoadStatus({ engine, parameters = {}, progress, active = false, minimal = false }: {
  engine: string; parameters?: Record<string, string | number>; progress?: RuntimeProgress; active?: boolean; minimal?: boolean;
}) {
  const { t } = useI18n();
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if (!active) return; const timer = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(timer); }, [active]);
  const estimate = estimates.estimates.find((item) => item.engine === engine && (!('model' in item) || item.model === (engine === 'rvc' ? parameters.model_id : parameters.model)) && (!('method' in item) || item.method === parameters.f0_method));
  const range = estimate ? `${Math.floor(estimate.seconds[0])}～${Math.ceil(estimate.seconds[1])}` : '';
  const waiting = active && progress && !['running', 'playing', 'completed', 'error', 'cancelled'].includes(progress.phase);
  const age = progress ? Math.max(0, (now - Date.parse(progress.observed_at)) / 1000) : 0;
  const elapsed = progress ? Math.floor((['generating', 'playing', 'postfx'].includes(progress.phase) ? progress.last_progress_seconds_ago : progress.elapsed_seconds) + (waiting ? age : 0)) : 0;
  const last = progress ? Math.floor(progress.last_progress_seconds_ago + (waiting ? age : 0)) : 0;
  const slow = waiting && estimate && ['environment', 'model_load', 'warmup'].includes(progress.phase) && elapsed > estimate.seconds[1];
  const phase = progress ? t(`progress.${progress.phase}`) : t('progress.environment');
  if (minimal) return <span className="load-mini" title={waiting ? t('load.wait', { phase, seconds: elapsed }) : t('load.estimate', { seconds: range || t('load.unmeasured') })}>{active && progress ? `${phase} · ${elapsed}s` : ''}</span>;
  return <div className="load-status" data-testid="load-status">
    <span className="field-caption">{t('load.title')}<HelpIcon label={t('load.title')} help="help.load"/></span>
    <span>{estimate ? t('load.estimate', { seconds: range }) : t('load.unmeasured')}</span>
    {active && progress && <div className="load-current" role="status">
      {progress.runtime_reused && <small>{t('load.reused')}</small>}
      <strong>{phase}{waiting ? ` · ${t('load.elapsed', { seconds: elapsed })}` : ''}</strong>
      <small>{t(progress.worker_alive === true ? 'load.alive' : progress.worker_alive === false ? 'load.exited' : 'load.preparing')} · {t('load.last', { seconds: last })}</small>
      {progress.load_seconds != null && <small>{t('load.measured', { seconds: progress.load_seconds.toFixed(1) })}</small>}
      {slow && <small className="waiting">{t('load.slow')}</small>}
    </div>}
  </div>;
}
