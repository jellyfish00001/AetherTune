// 真實 Desktop WebView2 → Rust IPC → TTS service → 播放路由的單句驗證。
// 會實際發聲；必須由操作人明確設定環境旗標，且不會自行關閉 App。
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

if (process.env.AETHERTUNE_NATIVE_AUDIO_SMOKE !== '1') {
  throw new Error('此腳本會送出真實 TTS；請設定 AETHERTUNE_NATIVE_AUDIO_SMOKE=1');
}

const artifactDir = fileURLToPath(new URL('../../artifacts/desktop/ui/', import.meta.url));
await mkdir(artifactDir, { recursive: true });
const reportPath = fileURLToPath(new URL('../../artifacts/desktop/ui/manual-tts-native-smoke.json', import.meta.url));
const screenshotPath = fileURLToPath(new URL('../../output/playwright/manual-tts-native-smoke.png', import.meta.url));
await mkdir(fileURLToPath(new URL('../../output/playwright/', import.meta.url)), { recursive: true });

const browser = await chromium.connectOverCDP(process.env.AETHERTUNE_CDP ?? 'http://127.0.0.1:9223');
const page = browser.contexts()[0].pages().find((candidate) => candidate.url().includes('tauri.localhost'));
assert.ok(page, '找不到本次 Desktop 的原生 WebView2 頁面');
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });

const invoke = (command) => page.evaluate((name) => window.__TAURI_INTERNALS__.invoke(name), command);
const startedAt = Date.now();
const phrase = 'AetherTune 輸出裝置測試。';
const transitions = [];
let report = { status: 'WAITING', started_at: new Date(startedAt).toISOString(), phrase, transitions };

try {
  assert.equal(await page.locator('main').getAttribute('data-native'), 'true');
  await page.getByRole('button', { name: 'Full', exact: true }).click();
  await page.getByRole('button', { name: 'WORKSPACE', exact: true }).click();
  assert.equal(await page.getByRole('button', { name: 'VOICE', exact: true }).count(), 0);
  assert.equal(await page.getByRole('button', { name: 'TRANSCRIPT', exact: true }).count(), 0);
  await page.getByLabel('Mode', { exact: true }).selectOption('text_to_speech');
  await page.getByLabel('TTS Output').waitFor({ state: 'visible' });
  await page.waitForFunction(() => {
    const select = document.querySelector('select[aria-label="TTS Output"]');
    return select && !select.disabled && select.value !== '';
  }, null, { timeout: 30000 });
  const output = await page.getByLabel('TTS Output').locator('option:checked').textContent();
  assert.ok(output?.includes('系統預設'), `未自動選中系統輸出：${output}`);
  assert.ok(!/CABLE|Voicemeeter/i.test(output), `系統預設是虛擬線路；停止實體喇叭 smoke：${output}`);
  await page.getByLabel('Voice profile').selectOption({ label: 'Reference Female' });
  const before = await invoke('speech_status');
  const existingIds = new Set(before.queue.map((item) => item.id));
  await page.getByLabel('Speech composer').fill(phrase);
  await page.screenshot({ path: screenshotPath });
  await page.getByRole('button', { name: 'Speak', exact: true }).click();

  let request;
  let snapshot;
  const deadline = Date.now() + 300000;
  while (Date.now() < deadline) {
    snapshot = await invoke('speech_status');
    request = snapshot.queue.find((item) => !existingIds.has(item.id) && item.text === phrase);
    if (request && transitions.at(-1)?.status !== request.status) {
      transitions.push({ at: new Date().toISOString(), status: request.status });
      console.log(`TTS ${request.id}: ${request.status}`);
    }
    if (request && ['completed', 'failed', 'cancelled'].includes(request.status)) break;
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }
  assert.ok(request, 'Speak 未建立可見的 Speech Queue request');
  report = {
    ...report,
    status: request.status,
    session_id: snapshot.session_id,
    request_id: request.id,
    route: request.route_snapshot,
    metrics: request.metrics,
    error: request.error ?? null,
    console_errors: errors,
    screenshot: screenshotPath,
  };
  assert.equal(request.status, 'completed', `TTS 未完成：${JSON.stringify(request.error)}`);
  assert.ok(request.metrics?.first_playback_audio_at, '缺少播放 callback 的首音時間');
  assert.ok(Number(request.metrics?.playback_seconds) > 0, '播放長度必須大於零');
  assert.equal(request.metrics?.output_name, request.route_snapshot?.output);
  assert.equal(request.metrics?.host_api, request.route_snapshot?.host_api);
  assert.deepEqual(errors, [], 'WebView2 有 console/page error');
  report.status = 'PASS';
} catch (error) {
  report.status = 'FAILED';
  report.failure = error instanceof Error ? error.message : String(error);
  throw error;
} finally {
  await writeFile(reportPath, JSON.stringify(report, null, 2));
  await browser.close();
  console.log(`native smoke report: ${reportPath}`);
}
