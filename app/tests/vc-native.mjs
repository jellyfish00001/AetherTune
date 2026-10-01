// 根目錄 exe 的四引擎 START／STOP 與可見狀態；不把環境音或開啟裝置當成人耳驗收。
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';

const dir = new URL('../../artifacts/desktop/vc-repair-20261001/native/', import.meta.url);
await mkdir(dir, { recursive: true });
const browser = await chromium.connectOverCDP(process.env.AETHERTUNE_CDP ?? 'http://127.0.0.1:9222');
const page = browser.contexts()[0].pages().find(page => /tauri.localhost/.test(page.url()));
assert.ok(page, '需使用內含前端的根目錄 exe');
const invoke = (name, args) => page.evaluate(({ name, args }) => window.__TAURI_INTERNALS__.invoke(name, args), { name, args });
const errors = [], network = [], results = [];
page.on('pageerror', error => errors.push(error.message));
page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
page.on('requestfailed', request => network.push({ url: request.url(), failure: request.failure() }));
async function waitForStatus(predicate, timeout = 150000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const status = await invoke('status');
    if (status.value === 'ERROR') throw new Error(JSON.stringify(status));
    if (predicate(status)) return status;
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  throw new Error(`等候狀態逾時：${JSON.stringify(await invoke('status'))}`);
}
try {
  await invoke('stop');
  const shell = await invoke('shell_status');
  await invoke('set_shell', { shell: { ...shell, mode: 'full', click_through: false } });
  await page.getByLabel('Mode', { exact: true }).selectOption('streaming_vc');
  await page.getByLabel('Host API', { exact: true }).selectOption('Windows DirectSound');
  await page.getByLabel('Input device', { exact: true }).selectOption('麥克風 (HyperX QuadCast S)');
  await page.getByLabel('Output device', { exact: true }).selectOption('CABLE Input (VB-Audio Virtual Cable)');
  await page.getByLabel('自己監聽', { exact: true }).uncheck();
  await page.locator('.vc-postfx').evaluate(element => { element.open = true; });
  await page.getByLabel('啟用音效', { exact: true }).check();
  for (const engine of ['meanvc2', 'xvc', 'seed-vc', 'rvc']) {
    await page.getByLabel('Engine', { exact: true }).selectOption(engine);
    if (engine === 'rvc') await page.getByLabel('RVC source_mode').selectOption('microphone');
    assert.equal(await page.getByLabel('Source WAV', { exact: true }).count(), 0);
    assert.ok(await page.getByRole('button', { name: '▶ START', exact: true }).isEnabled());
    const started = Date.now();
    await page.getByRole('button', { name: '▶ START', exact: true }).click();
    const running = await waitForStatus(status => status.value === 'RUNNING');
    assert.equal(running.engine_id, engine);
    assert.equal(running.adapter, 'stream_runner');
    assert.equal(await page.getByLabel('Engine', { exact: true }).isDisabled(), true);
    const withMetrics = await waitForStatus(status => Number(status.metrics?.blocks) >= 10, 15000);
    assert.ok(withMetrics.runtime?.gpu);
    assert.ok(Number.isFinite(withMetrics.metrics.p95_ms));
    await page.screenshot({ path: new URL(`${engine}-running.png`, dir).pathname.replace(/^\/(\w:)/, '$1') });
    await page.getByRole('button', { name: '■ STOP', exact: true }).click();
    const stopped = await waitForStatus(status => status.value === 'OFFLINE' && !status.service_alive, 15000);
    const logs = await invoke('logs');
    const pids = logs.filter(event => event.type === 'process_started').map(event => event.pid);
    results.push({ engine, status: 'PASS', start_metrics_stop_seconds: (Date.now() - started) / 1000,
      running: withMetrics, stopped, pids, logs, scope: 'native UI route/START/metrics/STOP; physical listening WAITING' });
    console.log(`PASS: ${engine} 原生 START → RUNNING/metrics → STOP`);
  }
  // 取消載入後仍能回到可操作狀態；不必等模型完成。
  await page.getByLabel('Engine', { exact: true }).selectOption('seed-vc');
  await page.getByRole('button', { name: '▶ START', exact: true }).click();
  await waitForStatus(status => status.value === 'LOADING', 15000);
  await page.getByRole('button', { name: '■ STOP', exact: true }).click();
  await waitForStatus(status => status.value === 'OFFLINE' && !status.service_alive, 15000);
  results.push({ assertion: 'LOADING cancel', status: 'PASS', stopped: await invoke('status') });
  assert.deepEqual(errors, []);
  assert.deepEqual(network, []);
  // 完成後留下直接可聽的實體路由，避免測試 CABLE 設定成為使用者無聲的原因。
  await page.getByLabel('Engine', { exact: true }).selectOption('rvc');
  await page.getByLabel('Output device', { exact: true }).selectOption('喇叭 (HyperX QuadCast S)');
  await page.getByLabel('啟用音效', { exact: true }).uncheck();
  await page.locator('.vc-postfx').evaluate(element => { element.open = false; });
  await page.locator('.content').evaluate(element => { element.scrollTop = 0; });
  await page.screenshot({ path: new URL('ready.png', dir).pathname.replace(/^\/(\w:)/, '$1') });
  await writeFile(new URL('report.json', dir), JSON.stringify({ status: 'PASS', url: page.url(),
    surface: 'root AetherTune.exe / native WebView2 CDP', viewport: await page.evaluate(() => ({ width: innerWidth, height: innerHeight, dpr: devicePixelRatio })),
    results, consoleErrors: errors, networkErrors: network, audio_verified: false }, null, 2));
} catch (error) {
  await invoke('stop').catch(() => {});
  await writeFile(new URL('report.json', dir), JSON.stringify({ status: 'BLOCKED', error: String(error), results, consoleErrors: errors, networkErrors: network, audio_verified: false }, null, 2));
  throw error;
} finally {
  await browser.close();
}
