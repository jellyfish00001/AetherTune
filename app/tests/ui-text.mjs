// 測試定位使用穩定 ID；只有顯示文案的斷言才查共用語系，預設繁體中文。
import { readFileSync } from 'node:fs';
const messages = JSON.parse(readFileSync(new URL('../src/locales/messages.json', import.meta.url), 'utf8'));
let testLocale = 'zh-TW';
export const setUiLocale = locale => { testLocale = locale === 'en' ? 'en' : 'zh-TW'; };
export const uiText = (key, locale = testLocale) => messages[key]?.[locale === 'en' ? 1 : 0] ?? key;
