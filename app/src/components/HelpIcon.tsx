import React, { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useI18n } from '../services/i18n';

export function HelpIcon({ help, label }: { help: string; label: string }) {
  const { t } = useI18n();
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [position, setPosition] = useState({ left: 8, top: 8 });
  const close = () => { clearTimeout(timer.current); setOpen(false); setPinned(false); };
  const show = () => {
    clearTimeout(timer.current);
    window.dispatchEvent(new CustomEvent('aethertune-help-open', { detail: id }));
    setOpen(true);
  };
  useEffect(() => {
    const other = (event: Event) => { if ((event as CustomEvent).detail !== id) close(); };
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape') close(); };
    window.addEventListener('aethertune-help-open', other);
    window.addEventListener('keydown', key);
    window.addEventListener('resize', close);
    return () => { clearTimeout(timer.current); window.removeEventListener('aethertune-help-open', other); window.removeEventListener('keydown', key); window.removeEventListener('resize', close); };
  }, [id]);
  useLayoutEffect(() => {
    if (!open) return;
    // Portal 避免 overflow 裁切；焦點自動捲動時同步移位，不把剛開啟的提示關掉。
    const reposition = () => {
      if (!button.current || !popup.current) return;
      const rect = button.current.getBoundingClientRect(), box = popup.current.getBoundingClientRect();
      setPosition({ left: Math.max(8, Math.min(rect.left, innerWidth - box.width - 8)), top: Math.max(8, Math.min(rect.bottom + 7 + box.height <= innerHeight - 8 ? rect.bottom + 7 : rect.top - box.height - 7, innerHeight - box.height - 8)) });
    };
    reposition();
    window.addEventListener('scroll', reposition, true);
    return () => window.removeEventListener('scroll', reposition, true);
  }, [open, help]);
  const leave = () => { if (!pinned) timer.current = setTimeout(() => setOpen(false), 160); };
  return <>
    <button ref={button} type="button" className="help-icon" aria-label={t('help.label', { label })} aria-describedby={open ? id : undefined} aria-expanded={open} onMouseEnter={show} onMouseLeave={leave} onFocus={show} onBlur={close} onClick={(event) => { event.preventDefault(); if (pinned) close(); else { show(); setPinned(true); } }}>ⓘ</button>
    {open && createPortal(<div ref={popup} id={id} role="tooltip" className="help-tooltip" style={position} onMouseEnter={() => clearTimeout(timer.current)} onMouseLeave={leave}>{t(help)}</div>, document.body)}
  </>;
}
