// 六引擎設定隔離、舊設定移轉、重載與重設；preview 不控制真實音訊。
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
const key = 'aethertune.audio-effects.v1';
const legacyKey = 'aethertune.vc-settings.v1';
const native = !!process.env.AETHERTUNE_CDP;
const browser = native ? await chromium.connectOverCDP(process.env.AETHERTUNE_CDP) : await chromium.launch({ channel: 'msedge', headless: true });
const page = native ? browser.contexts()[0].pages().find(p => /tauri.localhost/.test(p.url())) : await browser.newPage({ viewport: { width: 1040, height: 740 } });
const directory = new URL('../../artifacts/desktop/audio-effects-20261001/', import.meta.url);
await mkdir(directory, { recursive: true });
const errors = [], network = [];
page.on('pageerror', e => errors.push(e.message));
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
page.on('requestfailed', r => network.push(r.url()));
if (!native) {
  await page.addInitScript(() => {
    if (!sessionStorage.getItem('effects-migration-seeded')) {
      localStorage.setItem('aethertune.vc-settings.v1', JSON.stringify({ postfx: { enabled: true, wet: 0.57 } }));
      sessionStorage.setItem('effects-migration-seeded', 'true');
    }
  });
  await page.goto('http://127.0.0.1:1420/');
} else {
  const state = await page.evaluate(async () => ({ vc: await window.__TAURI_INTERNALS__.invoke('status'), speech: await window.__TAURI_INTERNALS__.invoke('speech_status') }));
  assert.equal(state.vc.service_alive, false);
  assert.ok(['IDLE', 'ERROR'].includes(state.speech.state));
}
await page.waitForSelector('main');
const original = native ? await page.evaluate(({ key, legacyKey }) => ({ effects: localStorage.getItem(key), legacy: localStorage.getItem(legacyKey) }), { key, legacyKey }) : null;
try {
  await page.getByRole('button', { name: 'SETTINGS', exact: true }).click();
  const select = page.getByLabel('音效引擎');
  if (!native) {
    assert.equal(await page.getByLabel('Post-FX wet').inputValue(), '0.57');
    assert.equal(await page.getByLabel('啟用音效').isChecked(), true);
    await select.selectOption('meanvc2');
    assert.equal(await page.getByLabel('啟用音效').isChecked(), false, '舊共用啟用狀態不得污染其他引擎');
  }
  const engines = ['rvc', 'meanvc2', 'xvc', 'seed-vc', 'cosyvoice', 'breeze'];
  const expected = {};
  for (const [index, engine] of engines.entries()) {
    await select.selectOption(engine);
    const wet = (index + 1) / 10;
    await page.getByLabel('Post-FX wet').fill(String(wet));
    await page.getByLabel('Post-FX wet').blur();
    await page.getByLabel('Post-FX low').fill(String(-index - 1));
    await page.getByLabel('Post-FX low').blur();
    await page.getByLabel('啟用音效').setChecked(index % 2 === 0);
    expected[engine] = { wet, low_db: -index - 1, enabled: index % 2 === 0 };
  }
  await page.reload();
  await page.getByRole('button', { name: 'SETTINGS', exact: true }).click();
  for (const engine of engines) {
    await page.getByLabel('音效引擎').selectOption(engine);
    assert.equal(Number(await page.getByLabel('Post-FX wet').inputValue()), expected[engine].wet);
    assert.equal(Number(await page.getByLabel('Post-FX low').inputValue()), expected[engine].low_db);
    assert.equal(await page.getByLabel('啟用音效').isChecked(), expected[engine].enabled);
  }
  await page.getByLabel('音效引擎').selectOption('rvc');
  await page.screenshot({ path: new URL(`${native ? 'native' : 'preview'}-settings.png`, directory).pathname.replace(/^\/(\w:)/, '$1') });
  await page.getByRole('button', { name: '重設此項目音效', exact: true }).click();
  assert.equal(await page.getByLabel('啟用音效').isChecked(), false);
  const records = await page.evaluate(key => JSON.parse(localStorage.getItem(key)), key);
  assert.equal(records.rvc.wet, 0.3);
  for (const engine of engines.slice(1)) assert.equal(records[engine].wet, expected[engine].wet, '重設僅影響目前項目');
  assert.equal(await page.getByLabel('Post-FX wet').count(), 1, '只有設定頁提供可編輯音效');
  await page.getByRole('button', { name: 'WORKSPACE', exact: true }).click();
  assert.equal(await page.getByLabel('Post-FX wet').count(), 0);
  await page.getByLabel('Engine', { exact: true }).selectOption('meanvc2');
  await page.getByRole('button', { name: 'Compact', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('main')?.classList.contains('compact'));
  await page.getByRole('button', { name: '調整音效', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('main')?.classList.contains('full'));
  assert.equal(await page.getByLabel('音效引擎').inputValue(), 'meanvc2');
  assert.equal(Number(await page.getByLabel('Post-FX wet').inputValue()), expected.meanvc2.wet);
  assert.deepEqual(errors, []);
  assert.deepEqual(network, []);
  const report = { status: 'PASS', scope: 'UI storage/engine isolation only, no audio', surface: native ? 'native WebView2' : 'Edge preview', url: page.url(), viewport: await page.evaluate(() => ({ width: innerWidth, height: innerHeight, dpr: devicePixelRatio })), engines: expected, checks: ['six independent engine records', 'reload persistence', 'negative EQ input', 'reset only current record', 'workspace entry selects current engine', ...(!native ? ['legacy migrates to RVC only'] : [])], consoleErrors: errors, networkErrors: network };
  await writeFile(new URL(`${native ? 'native' : 'preview'}-report.json`, directory), JSON.stringify(report, null, 2));
  console.log(`PASS: ${report.surface} audio-effects settings, engine isolation and persistence`);
} finally {
  if (native && original) {
    await page.evaluate(({ original, key, legacyKey }) => {
      for (const [name, value] of [[key, original.effects], [legacyKey, original.legacy]]) value === null ? localStorage.removeItem(name) : localStorage.setItem(name, value);
    }, { original, key, legacyKey });
    await page.reload();
  }
  await browser.close();
}
