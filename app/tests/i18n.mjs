import { chromium } from 'playwright';
import ts from 'typescript';
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const messages = JSON.parse(await readFile(new URL('src/locales/messages.json', root), 'utf8'));
// 檢查文案完整性與插值一致；新增 JSX 文案漏接翻譯時直接失敗。
const placeholders = text => [...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort();
for (const [key, translations] of Object.entries(messages)) {
  assert.equal(translations.length, 2, key);
  assert.ok(translations.every(value => typeof value === 'string' && value.length), key);
  assert.deepEqual(placeholders(translations[0]), placeholders(translations[1]), key);
}
for (const file of ['main.tsx', 'components/AudioEffectsSettings.tsx', 'components/RvcControls.tsx', 'components/VcAudioControls.tsx', 'components/SpeechWorkspace.tsx', 'services/i18n.tsx']) {
  const source = ts.createSourceFile(file, await readFile(new URL(`src/${file}`, root), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  function inspect(node) {
    if (ts.isJsxText(node) && /[\p{L}]/u.test(node.text)) assert.ok(['AetherTune', 'GPU', 'AETHERTUNE', '[T]'].includes(node.text.trim()), `${file}: untranslated JSX ${node.text}`);
    if (ts.isCallExpression(node) && node.expression.getText(source) === 't' && ts.isStringLiteral(node.arguments[0])) assert.ok(messages[node.arguments[0].text], `${file}: missing key ${node.arguments[0].text}`);
    ts.forEachChild(node, inspect);
  }
  inspect(source);
}

const directory = new URL('../../artifacts/desktop/i18n-20261001/', import.meta.url);
await mkdir(directory, { recursive: true });
const native = !!process.env.AETHERTUNE_CDP;
const browser = native ? await chromium.connectOverCDP(process.env.AETHERTUNE_CDP) : await chromium.launch({ channel: 'msedge', headless: true });
const page = native ? browser.contexts()[0].pages().find(page => /tauri.localhost/.test(page.url())) : await browser.newPage({ viewport: { width: 1040, height: 740 } });
assert.ok(page);
const errors = [], network = [], checks = [];
page.on('pageerror', error => errors.push(error.message));
page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
page.on('requestfailed', request => network.push(request.url()));
const invoke = (name, args) => page.evaluate(({ name, args }) => window.__TAURI_INTERNALS__.invoke(name, args), { name, args });
if (!native) await page.goto('http://127.0.0.1:1420/');
await page.waitForSelector('main');
const keys = ['aethertune.ui-language.v1', 'aethertune.vc-settings.v1', 'aethertune.audio-effects.v1'];
const original = native ? await page.evaluate(keys => Object.fromEntries(keys.map(key => [key, localStorage.getItem(key)])), keys) : null;
const originalSession = native ? await page.evaluate(() => Object.fromEntries(Object.keys(sessionStorage).filter(key => key.startsWith('aethertune:speech:')).map(key => [key, sessionStorage.getItem(key)]))) : null;
const shell = native ? await invoke('shell_status') : null;
try {
  if (native) {
    const vc = await invoke('status'), speech = await invoke('speech_status');
    assert.equal(vc.service_alive, false, 'Do not interrupt active audio');
    assert.ok(['IDLE', 'ERROR'].includes(speech.state));
    await invoke('set_shell', { shell: { ...shell, mode: 'full', click_through: false, quick_input: false } });
  }
  await page.getByTestId('nav-SETTINGS').click();
  await page.getByTestId('ui-language').selectOption('zh-TW');
  assert.equal(await page.locator('html').getAttribute('lang'), 'zh-Hant');
  assert.equal(await page.getByRole('heading', { name: '介面語言', exact: true }).count(), 1);
  const effects = await page.evaluate(() => localStorage.getItem('aethertune.audio-effects.v1'));
  await page.getByTestId('ui-language').selectOption('en');
  assert.equal(await page.locator('html').getAttribute('lang'), 'en');
  assert.equal(await page.getByRole('heading', { name: 'Interface language', exact: true }).count(), 1);
  assert.equal(await page.getByRole('heading', { name: 'Audio effects', exact: true }).count(), 1);
  assert.equal(await page.getByTestId('control:啟用音效').getAttribute('aria-label'), 'Enable effects');
  assert.equal(await page.getByTestId('control:Post-FX wet').getAttribute('aria-label'), 'Dry / wet blend');
  checks.push('zh-Hant/en labels and accessible names switch immediately');
  await page.screenshot({ path: new URL(`${native ? 'native' : 'preview'}-en-settings.png`, directory).pathname.replace(/^\/(\w:)/, '$1') });
  if (native) {
    for (let attempt = 0; attempt < 40 && (await invoke('window_status')).ui_language !== 'en'; attempt++) await new Promise(resolve => setTimeout(resolve, 100));
    assert.equal((await invoke('window_status')).ui_language, 'en');
    const tray = await invoke('set_ui_language', { language: 'en' });
    assert.deepEqual(tray.labels, ['Open AetherTune', 'Show overlay', 'Start / stop conversion', 'Disable click-through', 'Exit']);
    await assert.rejects(invoke('set_ui_language', { language: 'unsupported' }));
    checks.push('actual native menu item text and invalid locale rejection');
  }
  await page.reload();
  await page.getByTestId('nav-SETTINGS').click();
  assert.equal(await page.getByTestId('ui-language').inputValue(), 'en');
  assert.equal(await page.locator('html').getAttribute('lang'), 'en');
  checks.push('reload persistence');
  await page.getByTestId('nav-LIVE').click();
  for (const engine of ['rvc', 'seed-vc', 'meanvc2', 'xvc']) {
    await page.getByTestId('control:Engine').selectOption(engine);
    assert.equal(await page.getByRole('button', { name: '▶ Start', exact: true }).count(), 1);
    assert.equal(await page.getByTestId('control:Mode').inputValue(), 'streaming_vc');
  }
  await page.getByTestId('control:Mode').selectOption('text_to_speech');
  const composer = page.getByTestId('control:Speech composer');
  const text = '保留使用者原文 · preserve my draft';
  await composer.fill(text);
  assert.equal(await page.getByRole('heading', { name: 'Turn text into speech.', exact: true }).count(), 1);
  assert.equal(await page.getByTestId('speech-state').textContent(), 'Idle');
  assert.equal(await page.getByTestId('control:Voice profile').locator('option:checked').textContent(), 'Mandarin reference (official sample)');
  await page.getByTestId('control:Engine').selectOption('breeze');
  assert.equal(await page.getByTestId('control:Voice profile').locator('option:checked').textContent(), 'Mandarin female reference (non-commercial test)');
  await page.getByTestId('control:Engine').selectOption('cosyvoice');
  await page.getByTestId('window-mode-compact').click();
  await page.waitForFunction(() => document.querySelector('main')?.classList.contains('compact'));
  if (!native) await page.setViewportSize({ width: 420, height: 490 });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'English Compact must not scroll horizontally');
  await page.getByTestId('window-mode-mini').click();
  await page.waitForFunction(() => document.querySelector('main')?.classList.contains('mini'));
  if (!native) await page.setViewportSize({ width: 420, height: 74 });
  await page.getByTestId('control:開啟 TTS Quick Input').click();
  if (!native) await page.setViewportSize({ width: 420, height: 260 });
  const close = page.getByRole('button', { name: 'Close quick input', exact: true });
  await close.waitFor({ state: 'visible' });
  if (native) await page.waitForFunction(() => innerHeight >= 260);
  assert.equal(await close.count(), 1);
  const closeRect = await close.boundingBox();
  assert.ok(closeRect && closeRect.y + closeRect.height <= await page.evaluate(() => innerHeight));
  assert.equal(await page.getByTestId('control:Compact quick input').inputValue(), text);
  await close.click();
  await page.getByTestId('control:展開 Compact').click();
  await page.getByTestId('window-mode-full').click();
  if (!native) await page.setViewportSize({ width: 1040, height: 740 });
  checks.push('English Compact 420x490 and Mini quick input 420x260');
  const vcSettings = await page.evaluate(() => localStorage.getItem('aethertune.vc-settings.v1'));
  await page.getByTestId('nav-SETTINGS').click();
  await page.getByTestId('ui-language').selectOption('zh-TW');
  await page.getByTestId('nav-LIVE').click();
  assert.equal(await composer.inputValue(), text, 'Language must not replace user text');
  assert.equal(await page.getByRole('button', { name: '發聲', exact: true }).count(), 1);
  assert.equal(await page.getByTestId('speech-state').textContent(), '待命');
  assert.equal(await page.evaluate(() => localStorage.getItem('aethertune.audio-effects.v1')), effects);
  assert.equal(await page.evaluate(() => localStorage.getItem('aethertune.vc-settings.v1')), vcSettings);
  checks.push('six engine display paths; user text, effects and route records unchanged');
  await page.getByTestId('window-mode-compact').click();
  await page.getByTestId('window-mode-mini').click();
  await page.getByTestId('control:開啟 TTS Quick Input').click();
  assert.equal(await page.getByTestId('control:Compact quick input').inputValue(), text);
  await page.getByTestId('control:Close quick input').click();
  await page.getByTestId('control:展開 Compact').click();
  await page.getByTestId('window-mode-full').click();
  if (!native) {
    for (const [stored, expected] of [['unsupported', 'zh-Hant'], ['en', 'en']]) {
      await page.evaluate(value => localStorage.setItem('aethertune.ui-language.v1', value), stored);
      await page.reload();
      assert.equal(await page.locator('html').getAttribute('lang'), expected);
    }
    checks.push('invalid stored locale safely falls back to Traditional Chinese');
    await page.getByTestId('nav-SETTINGS').click();
    await page.getByTestId('ui-language').selectOption('zh-TW');
    await page.screenshot({ path: new URL('preview-zh-settings.png', directory).pathname.replace(/^\/(\w:)/, '$1') });
    await page.addInitScript(() => {
      const write = Storage.prototype.setItem;
      Storage.prototype.setItem = function(key, value) { if (key === 'aethertune.ui-language.v1') throw new DOMException('test quota', 'QuotaExceededError'); return write.call(this, key, value); };
    });
    await page.reload();
    await page.getByTestId('nav-SETTINGS').click();
    await page.getByRole('alert').filter({ hasText: '語言選擇儲存失敗' }).waitFor();
    await page.getByTestId('ui-language').selectOption('en');
    await page.getByRole('alert').filter({ hasText: 'Could not save the language choice.' }).waitFor();
    assert.equal(await page.locator('html').getAttribute('lang'), 'en');
    assert.equal(await page.evaluate(() => localStorage.getItem('aethertune.ui-language.v1')), 'zh-TW');
    checks.push('storage failure shown in both languages; session choice remains usable');
  }
  assert.deepEqual(errors, []);
  assert.deepEqual(network, []);
  await writeFile(new URL(`${native ? 'native' : 'preview'}-report.json`, directory), JSON.stringify({ status: 'PASS', surface: native ? 'native WebView2' : 'Edge preview', url: page.url(), viewport: await page.evaluate(() => ({ width: innerWidth, height: innerHeight, dpr: devicePixelRatio })), locales: ['zh-TW', 'en'], messages: Object.keys(messages).length, checks, consoleErrors: errors, networkErrors: network, scope: 'UI language only; no audio generation or microphone test' }, null, 2));
} finally {
  if (native) {
    await page.evaluate(original => { for (const [key, value] of Object.entries(original)) { if (value === null) localStorage.removeItem(key); else localStorage.setItem(key, value); } }, original);
    await page.evaluate(original => { for (const key of Object.keys(sessionStorage).filter(key => key.startsWith('aethertune:speech:'))) sessionStorage.removeItem(key); for (const [key, value] of Object.entries(original)) sessionStorage.setItem(key, value); }, originalSession);
    await page.reload();
    await invoke('set_shell', { shell: { ...shell, click_through: false, quick_input: false } });
  }
  await browser.close();
}
console.log(`PASS: ${native ? 'native' : 'preview'} interface languages and persistence`);
