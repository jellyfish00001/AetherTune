import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { command, native } from './desktop';
import catalog from '../locales/messages.json';
const messages: Record<string, readonly string[]> = catalog;

export type Locale = 'zh-TW' | 'en';
export const localeStorageKey = 'aethertune.ui-language.v1';
export const locales: { id: Locale; name: string }[] = [{ id: 'zh-TW', name: '繁體中文' }, { id: 'en', name: 'English' }];
export function translate(locale: Locale, key: string, values: Record<string, string | number> = {}): string {
  const text = messages[key]?.[locale === 'en' ? 1 : 0] ?? key;
  // 只代換文案的具名欄位；使用者文字、裝置名稱與路徑均以 React 文字節點呈現。
  return text.replace(/\{(\w+)\}/g, (match, name: string) => Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : match);
}
function readLocale(): Locale {
  try { return localStorage.getItem(localeStorageKey) === 'en' ? 'en' : 'zh-TW'; } catch { return 'zh-TW'; }
}
type Translator = (key: string, values?: Record<string, string | number>) => string;
const I18n = createContext<{ locale: Locale; setLocale: (locale: Locale) => void; t: Translator; diagnostic: (message: string) => string; saveError: boolean; trayError: string } | null>(null);
export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocale] = useState<Locale>(readLocale);
  const [saveError, setSaveError] = useState(false);
  const [trayError, setTrayError] = useState('');
  const t = useCallback<Translator>((key, values) => translate(locale, key, values), [locale]);
  const diagnostic = useCallback((message: string) => {
    for (const [prefix, key] of [['Speech status WAITING：', 'speech.statusError'], ['speech-event WAITING：', 'speech.eventError']]) {
      if (message.startsWith(prefix)) return translate(locale, key, { error: message.slice(prefix.length) });
    }
    return translate(locale, message);
  }, [locale]);
  useEffect(() => {
    document.documentElement.lang = locale === 'en' ? 'en' : 'zh-Hant';
    try { localStorage.setItem(localeStorageKey, locale); setSaveError(false); } catch { setSaveError(true); }
    let disposed = false;
    if (native) void command('set_ui_language', { language: locale }).then(() => { if (!disposed) setTrayError(''); }).catch((reason) => { if (!disposed) setTrayError(String(reason)); });
    return () => { disposed = true; };
  }, [locale]);
  return <I18n.Provider value={{ locale, setLocale, t, diagnostic, saveError, trayError }}>{children}</I18n.Provider>;
}
export function useI18n() { const value = useContext(I18n); if (!value) throw new Error('LanguageProvider is required'); return value; }
export function LanguageSettings() {
  const { locale, setLocale, t, saveError, trayError } = useI18n();
  return <section className="panel language-settings"><h1>{t('language.title')}</h1>
    <label>{t('language.select')}<select data-testid="ui-language" aria-label={t('language.select')} value={locale} onChange={(event) => setLocale(event.target.value as Locale)}>{locales.map(({ id, name }) => <option key={id} value={id}>{name}</option>)}</select></label>
    <p className="hint">{t('language.help')}</p>
    {saveError && <p role="alert" className="error">{t('language.saveError')}</p>}
    {trayError && <p role="alert" className="error">{t('language.trayError', { error: trayError })}</p>}
  </section>;
}
