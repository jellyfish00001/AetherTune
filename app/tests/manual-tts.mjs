// Manual TTS UI regression. The second pass deliberately injects a Tauri IPC mock;
// it verifies request shape and UI rejection behavior, and is not live audio evidence.
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';

const baseUrl = process.env.AETHERTUNE_URL ?? 'http://127.0.0.1:1420/';
const artifactDir = new URL('../../artifacts/desktop/ui/', import.meta.url);
await mkdir(artifactDir, { recursive: true });

function wireDiagnostics(page) {
  const errors = [];
  const network = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('requestfailed', (request) => network.push({ url: request.url(), failure: request.failure() }));
  return { errors, network };
}

async function selectTtsMode(page, expectedProfiles) {
  const mode = page.getByLabel('Mode', { exact: true });
  await mode.selectOption('speech_reconstruction');
  await page.waitForFunction(() => document.querySelector('[data-speech-mode="speech_reconstruction"]') !== null);
  assert.deepEqual(await page.getByLabel('Engine', { exact: true }).locator('option').allTextContents(), ['CosyVoice', 'Breeze TTS 2']);
  assert.equal(await page.getByLabel('Input', { exact: true }).count(), 0);
  if (expectedProfiles) assert.deepEqual(await page.getByLabel('Voice profile').locator('option').allTextContents(), expectedProfiles);
}

async function previewPass() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1040, height: 740 } });
  const diagnostics = wireDiagnostics(page);
  await page.goto(baseUrl);
  await page.waitForSelector('main');
  assert.equal(await page.locator('main').getAttribute('data-native'), 'false');
  await selectTtsMode(page, ['中文參考聲音（官方範例）', '中文女聲參考（非商用測試）', '日語女聲參考（待核對）', '日語男聲參考（待核對）']);
  assert.equal(await page.getByLabel('Voice profile').locator('option:checked').textContent(), '中文參考聲音（官方範例）');
  await page.getByLabel('Engine', { exact: true }).selectOption('breeze');
  assert.equal(await page.getByLabel('Voice profile').locator('option:checked').textContent(), '中文女聲參考（非商用測試）');
  await page.getByLabel('Engine', { exact: true }).selectOption('cosyvoice');
  await page.getByLabel('Voice profile').selectOption('reference-female');
  assert.ok(await page.getByText('這是日語參考聲音', { exact: false }).isVisible());
  await page.getByLabel('Voice profile').selectOption('official-cosyvoice-sample');
  assert.equal(await page.locator('.speech-settings').count(), 0);
  assert.equal(await page.getByRole('button', { name: 'Speak', exact: true }).isDisabled(), true);
  assert.equal(await page.getByRole('button', { name: 'Add to Queue', exact: true }).isDisabled(), true);
  assert.equal(await page.getByText('CosyVoice3 · PLANNED', { exact: true }).count(), 0);

  const composer = page.getByLabel('Speech composer');
  await composer.fill('preview line one');
  await composer.press('Shift+Enter');
  await composer.type('preview line two');
  assert.equal(await composer.inputValue(), 'preview line one\npreview line two');
  await page.getByRole('button', { name: 'Clear', exact: true }).click();
  assert.equal(await composer.inputValue(), '');

  await page.getByRole('button', { name: 'Compact', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('main')?.classList.contains('compact'));
  await page.setViewportSize({ width: 420, height: 490 });
  assert.ok(await page.getByLabel('Speech composer').isVisible());
  await page.screenshot({ path: new URL('manual-tts-preview-compact.png', artifactDir).pathname.replace(/^\/(\w:)/, '$1') });
  await page.getByRole('button', { name: 'Mini', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('main')?.classList.contains('mini'));
  await page.setViewportSize({ width: 420, height: 74 });
  assert.deepEqual(await page.evaluate(() => ({ width: innerWidth, height: innerHeight })), { width: 420, height: 74 });
  await page.getByRole('button', { name: '開啟 TTS Quick Input' }).click();
  await page.setViewportSize({ width: 420, height: 260 });
  assert.ok(await page.getByTestId('speech-quick-popup').isVisible());
  assert.equal(await page.getByRole('button', { name: 'Speak', exact: true }).isDisabled(), true);
  assert.equal(await page.getByRole('button', { name: 'Add to Queue', exact: true }).count(), 0);
  const popupBox = await page.getByTestId('speech-quick-popup').boundingBox();
  const closeBox = await page.getByRole('button', { name: 'Close quick input' }).boundingBox();
  const speakBox = await page.getByRole('button', { name: 'Speak', exact: true }).boundingBox();
  assert.ok(popupBox && popupBox.y >= 74 && popupBox.y + popupBox.height <= 260);
  assert.ok(closeBox && closeBox.y + closeBox.height <= 260);
  assert.ok(speakBox && speakBox.y + speakBox.height <= 260);
  await page.screenshot({ path: new URL('manual-tts-preview-mini-quick.png', artifactDir).pathname.replace(/^\/(\w:)/, '$1') });
  await page.getByRole('button', { name: 'Close quick input' }).click();
  await page.getByRole('button', { name: '展開 Compact' }).click();
  await page.getByRole('button', { name: 'Full', exact: true }).click();
  await page.setViewportSize({ width: 1040, height: 740 });
  assert.equal(await page.getByRole('button', { name: 'VOICE', exact: true }).count(), 0);
  assert.equal(await page.getByRole('button', { name: 'TRANSCRIPT', exact: true }).count(), 0);
  assert.equal(await page.getByRole('button', { name: 'AUDIO', exact: true }).count(), 0);
  assert.ok(await page.getByText('僅顯示已完成的播放', { exact: true }).isVisible());
  await page.getByRole('button', { name: 'SETTINGS', exact: true }).click();
  assert.equal(await page.locator('.speech-settings').count(), 1);
  assert.equal(await page.getByLabel('Enter to send').isDisabled(), true);
  await page.getByRole('button', { name: 'WORKSPACE', exact: true }).click();
  assert.deepEqual(diagnostics.errors, []);
  assert.deepEqual(diagnostics.network, []);
  await page.screenshot({ path: new URL('manual-tts-preview-full.png', artifactDir).pathname.replace(/^\/(\w:)/, '$1') });
  await browser.close();
  return { status: 'PASS', consoleErrors: diagnostics.errors, networkErrors: diagnostics.network };
}

async function mockTauri(page) {
  const rvc = JSON.parse(await readFile(new URL('../../contracts/engines/rvc.json', import.meta.url), 'utf8'));
  await page.addInitScript(({ rvc }) => {
    window.isTauri = true;
    const callbacks = new Map();
    let nextCallback = 1;
    let shell = { mode: 'full', opacity: 0.94, always_on_top: false, locked: false, click_through: false, quick_input: false, visibility_hotkey: 'Ctrl+Alt+A', voice_hotkey: 'Ctrl+Alt+V' };
    const snapshot = { session_id: 'mock-session', state: 'IDLE', queue: [], transcript: [], profiles: [{ id: 'reference-male', name: 'Reference Male', engines: ['cosyvoice', 'breeze'], status: 'WAITING', metadata: { review_status: 'WAITING', notes: 'mock profile metadata' }, references: { cosyvoice: { audio_path: 'dataset/reference-voices/voice-male-m1.wav', text_path: 'tools/fixtures/cosyvoice/reference-male-text.txt', metadata_status: 'WAITING' }, breeze: { audio_path: 'dataset/reference-voices/voice-male-m1.wav', text_path: 'tools/fixtures/breeze-reference-male-text.txt', metadata_status: 'DRAFT' } } }], settings: { interrupt_policy: 'queue', enter_to_send: true }, recent_phrases: ['mock recent phrase'], favorites: [], mic_enabled: false, capabilities: { microphone: 'WAITING', manual_text: 'implemented', agent_reply: 'PLANNED' } };
    window.__speechMockActions = [];
    window.__speechMockReject = false;
    window.__speechMockBuffering = false;
    window.__speechMockQueueError = false;
    window.__speechMockMonitorError = false;
    window.__rvcMockStarts = [];
    let runnerStatus = { value: 'OFFLINE', engine_id: null, reason: 'mock', audio_verified: false, service_alive: false };
    const speechStatus = () => {
      if (window.__speechMockMonitorError) return { ...snapshot, queue: [{ id: 'monitor-warning', session_id: snapshot.session_id, source: 'manual', text: 'primary completed with monitor warning', engine_id: 'cosyvoice', voice_profile_id: 'reference-male', created_at: '2026-09-30T00:00:00Z', status: 'completed', priority: 0, metrics: { monitor_status: 'failed', monitor_error: 'DEVICE_NOT_FOUND: mock headphones' } }] };
      if (window.__speechMockBuffering) return { ...snapshot, state: 'BUFFERING', current_request_id: 'current-ready', queue: [{ id: 'current-ready', session_id: snapshot.session_id, source: 'manual', text: 'buffering current item', engine_id: 'cosyvoice', voice_profile_id: 'reference-male', created_at: '2026-09-27T00:00:00Z', status: 'ready', priority: 0 }, { id: 'queued-1', session_id: snapshot.session_id, source: 'manual', text: 'queued pending item', engine_id: 'cosyvoice', voice_profile_id: 'reference-male', created_at: '2026-09-27T00:00:00Z', status: 'queued', priority: 0 }] };
      if (window.__speechMockQueueError) return { ...snapshot, queue: [{ id: 'queued-1', session_id: snapshot.session_id, source: 'manual', text: 'queued pending item', engine_id: 'cosyvoice', voice_profile_id: 'reference-male', created_at: '2026-09-27T00:00:00Z', status: 'queued', priority: 0 }, { id: 'failed-1', session_id: snapshot.session_id, source: 'manual', text: 'failed queue item', engine_id: 'cosyvoice', voice_profile_id: 'reference-male', created_at: '2026-09-27T00:00:00Z', status: 'failed', priority: 0, error: { code: 'TTS_FAILED', message: 'mock backend failure' } }] };
      return snapshot;
    };
    const manifests = [
      { id: 'seed-vc', name: 'Seed-VC', capabilities: ['realtime_vc'], classification: 'CANDIDATE', adapter: 'temporary_gui', implementation: 'skeleton', limitations: [], parameters: [] },
      { id: 'cosyvoice', name: 'CosyVoice', capabilities: ['speech_reconstruction', 'text_to_speech'], classification: 'WAITING', adapter: 'planned', implementation: 'planned', limitations: [], parameters: [] },
      { id: 'breeze', name: 'Breeze TTS 2', capabilities: ['speech_reconstruction', 'text_to_speech'], classification: 'WAITING', adapter: 'planned', implementation: 'planned', limitations: [], parameters: [] },
      rvc,
    ];
    const devices = { inputs: [{ name: '麥克風 (HyperX QuadCast S)', host_api: 'Windows DirectSound', channels: 1, is_default: true, selectable: true }], outputs: [{ name: 'CABLE Input (VB-Audio Virtual Cable)', host_api: 'Windows DirectSound', channels: 2, is_default: false, selectable: true }, { name: '喇叭 (HyperX QuadCast S)', host_api: 'MME', channels: 2, is_default: true, selectable: true }] };
    devices.outputs.push(
      { name: '喇叭 (HyperX QuadCast S)', host_api: 'Windows WASAPI', channels: 2, is_default: false, selectable: true },
      { name: 'CABLE Input (VB-Audio Virtual C', host_api: 'MME', channels: 2, is_default: false, selectable: true },
      { name: 'Microsoft 音效對應表 - Output', host_api: 'MME', channels: 2, is_default: false, selectable: true },
      { name: 'Output (Voicemeeter Point 1)', host_api: 'Windows WDM-KS', channels: 8, is_default: false, selectable: true },
      { name: 'Voicemeeter In 1 (VB-Audio Voicemeeter VAIO)', host_api: 'Windows DirectSound', channels: 8, is_default: false, selectable: true },
      { name: 'CABLE In 16ch (VB-Audio Virtual Cable)', host_api: 'Windows DirectSound', channels: 16, is_default: false, selectable: true },
    );
    const invoke = async (command, args = {}) => {
      if (command === 'discover') return manifests;
      if (command === 'shell_status') return shell;
      if (command === 'set_shell') { shell = args.shell; return null; }
      if (command === 'status') return runnerStatus;
      if (command === 'start') { window.__rvcMockStarts.push(args); runnerStatus = { ...runnerStatus, value: 'RUNNING', engine_id: args.engine, service_alive: true }; return runnerStatus; }
      if (command === 'stop') { runnerStatus = { ...runnerStatus, value: 'OFFLINE', service_alive: false }; return runnerStatus; }
      if (command === 'logs') return [];
      if (command === 'window_status') return { size: { width: 1040, height: 740 }, position: { x: 0, y: 0 }, scale_factor: 1, visible: true, always_on_top: false, decorated: false, native_click_through: false, tray_registered: true };
      if (command === 'speech_status') return speechStatus();
      if (command === 'speech_action') {
        window.__speechMockActions.push(args);
        if (window.__speechMockReject) throw new Error('MOCK_REJECT');
        if (args.action?.action === 'audio_devices') return { accepted: true, result: devices };
        if (args.action?.action === 'settings') Object.assign(snapshot.settings, args.action.settings);
        return { accepted: true };
      }
      return null;
    };
    window.__TAURI_INTERNALS__ = {
      invoke,
      transformCallback: (callback) => { const id = nextCallback++; callbacks.set(id, callback); return id; },
      unregisterCallback: (id) => callbacks.delete(id),
      runCallback: (id, payload) => callbacks.get(id)?.(payload),
    };
    window.__TAURI_EVENT_PLUGIN_INTERNALS__ = { unregisterListener: () => undefined };
  }, { rvc });
}

async function mockPass() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1040, height: 740 } });
  const diagnostics = wireDiagnostics(page);
  await mockTauri(page);
  await page.goto(baseUrl);
  await page.waitForSelector('main[data-native="true"]');
  await page.getByLabel('Input device').waitFor({ state: 'visible' });
  await page.waitForFunction(() => document.querySelector('select[aria-label="Input device"]')?.querySelectorAll('option').length > 1);
  assert.equal(await page.getByLabel('Input device').inputValue(), '麥克風 (HyperX QuadCast S)');
  await selectTtsMode(page, ['Reference Male']);
  await page.waitForFunction(() => document.querySelector('select[aria-label="TTS Output"]')?.value === '1');
  assert.ok((await page.getByLabel('TTS Output').locator('option:checked').textContent()).includes('系統預設'));
  // 同一裝置只列一次；展開／收起進階選項不能改掉使用者選中的 Host API。
  const outputSelect = page.getByLabel('TTS Output');
  assert.equal(await outputSelect.locator('option').count(), 3);
  assert.equal((await outputSelect.locator('option').allTextContents()).some((label) => /WASAPI|WDM-KS|16ch|音效對應表/.test(label)), false);
  await page.getByLabel('顯示進階輸出裝置').check();
  assert.equal(await outputSelect.locator('option').count(), 9);
  await outputSelect.selectOption('2');
  await page.getByLabel('顯示進階輸出裝置').uncheck();
  assert.equal(await outputSelect.inputValue(), '2');
  await page.getByRole('button', { name: '重新掃描裝置', exact: true }).click();
  assert.equal(await outputSelect.inputValue(), '2');
  const routeComposer = page.getByLabel('Speech composer');
  await routeComposer.fill('selected output remains explicit');
  await page.getByRole('button', { name: 'Speak', exact: true }).click();
  const selectedRoute = await page.evaluate(() => window.__speechMockActions.at(-1).action.request.metadata.route);
  assert.equal(selectedRoute.host_api, 'Windows WASAPI');
  assert.equal(selectedRoute.output, '喇叭 (HyperX QuadCast S)');
  await outputSelect.selectOption('0');
  assert.equal(await outputSelect.locator('option:checked').textContent(), 'CABLE Input (VB-Audio Virtual Cable)');
  // 監聽預設關閉；啟用只加入獨立實體 route，不改掉 CABLE 主輸出。
  const selfMonitor = page.getByLabel('自己監聽', { exact: true });
  assert.equal(await selfMonitor.isChecked(), false);
  assert.equal(selectedRoute.monitor.enabled, false);
  await selfMonitor.check();
  const monitorSelect = page.getByLabel('監聽裝置', { exact: true });
  assert.equal(await monitorSelect.locator('option').count(), 2);
  assert.equal((await monitorSelect.locator('option').allTextContents()).some((label) => /CABLE|Voicemeeter|WASAPI/.test(label)), false);
  await routeComposer.fill('send and monitor separately');
  await page.getByRole('button', { name: 'Speak', exact: true }).click();
  const monitoredRoute = await page.evaluate(() => window.__speechMockActions.at(-1).action.request.metadata.route);
  assert.equal(monitoredRoute.output, 'CABLE Input (VB-Audio Virtual Cable)');
  assert.deepEqual(monitoredRoute.monitor, { enabled: true, output: '喇叭 (HyperX QuadCast S)', host_api: 'MME' });
  await page.getByRole('button', { name: '重新掃描裝置', exact: true }).click();
  assert.equal(await selfMonitor.isChecked(), true);
  assert.equal(await monitorSelect.inputValue(), '1');
  await page.getByRole('button', { name: 'Compact', exact: true }).click();
  await page.setViewportSize({ width: 420, height: 490 });
  assert.equal(await selfMonitor.isChecked(), true);
  await monitorSelect.scrollIntoViewIfNeeded();
  assert.ok((await monitorSelect.boundingBox()).width > 100);
  await page.screenshot({ path: new URL('../../output/playwright/self-monitor-compact-mock.png', import.meta.url).pathname.replace(/^\/(\w:)/, '$1') });
  await page.getByRole('button', { name: 'Full', exact: true }).click();
  await page.setViewportSize({ width: 1040, height: 740 });
  await page.locator('.speech-composer').screenshot({ path: new URL('../../output/playwright/self-monitor-mock.png', import.meta.url).pathname.replace(/^\/(\w:)/, '$1') });
  await selfMonitor.uncheck();
  await routeComposer.fill('send without monitor');
  await page.getByRole('button', { name: 'Speak', exact: true }).click();
  assert.equal((await page.evaluate(() => window.__speechMockActions.at(-1).action.request.metadata.route)).monitor.enabled, false);
  await page.evaluate(() => { window.__speechMockMonitorError = true; });
  await page.getByText('主輸出已完成，自己監聽失敗：DEVICE_NOT_FOUND: mock headphones', { exact: true }).waitFor();
  await page.evaluate(() => { window.__speechMockMonitorError = false; });
  await page.getByLabel('顯示進階輸出裝置').check();
  await outputSelect.selectOption('1');
  await page.getByLabel('顯示進階輸出裝置').uncheck();
  await page.evaluate(() => { window.__speechMockActions = []; });
  await mkdir(new URL('../../output/playwright/', import.meta.url), { recursive: true });
  await page.locator('.composer-output').screenshot({ path: new URL('../../output/playwright/output-device-cleanup-mock.png', import.meta.url).pathname.replace(/^\/(\w:)/, '$1') });
  const composer = page.getByLabel('Speech composer');

  await composer.fill('enter sends through speech action');
  await composer.press('Enter');
  await page.waitForFunction(() => window.__speechMockActions?.some((entry) => entry.action?.action === 'submit'));
  assert.equal(await composer.inputValue(), '');
  const enterAction = await page.evaluate(() => window.__speechMockActions.at(-1));
  assert.equal(enterAction.action.action, 'submit');
  assert.equal(enterAction.action.enqueue, false);
  assert.equal(enterAction.action.request.source, 'manual');
  assert.equal(enterAction.action.request.metadata.route.output, '喇叭 (HyperX QuadCast S)');
  assert.equal(enterAction.action.request.metadata.route.host_api, 'MME');
  assert.equal(enterAction.action.request.metadata.route.rack_profile_id, 'seed-vc-neutral');

  await composer.fill('explicit queue action');
  await page.getByRole('button', { name: 'Add to Queue', exact: true }).click();
  await page.waitForFunction(() => window.__speechMockActions?.some((entry) => entry.action?.action === 'submit' && entry.action.enqueue === true));
  const queueAction = await page.evaluate(() => window.__speechMockActions.at(-1));
  assert.equal(queueAction.action.enqueue, true);

  const beforeIme = await page.evaluate(() => window.__speechMockActions.length);
  await composer.fill('ime composing');
  await composer.evaluate((element) => {
    element.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
    element.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, isComposing: true }));
    element.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true }));
  });
  await page.waitForTimeout(100);
  assert.equal(await page.evaluate(() => window.__speechMockActions.length), beforeIme);
  assert.equal(await composer.inputValue(), 'ime composing');

  await page.getByRole('button', { name: 'SETTINGS', exact: true }).click();
  const enterSetting = page.getByLabel('Enter to send');
  await enterSetting.uncheck();
  await page.waitForFunction(() => window.__speechMockActions?.some((entry) => entry.action?.action === 'settings'));
  await page.getByRole('button', { name: 'WORKSPACE', exact: true }).click();
  await composer.evaluate((element) => { element.focus(); element.setSelectionRange(element.value.length, element.value.length); });
  await composer.press('Enter');
  assert.equal(await composer.inputValue(), 'ime composing\n');
  await composer.press('Shift+Enter');
  assert.equal(await composer.inputValue(), 'ime composing\n\n');

  await page.evaluate(() => { window.__speechMockBuffering = true; });
  await page.waitForFunction(() => document.querySelector('.queue-current')?.textContent?.includes('CURRENT · ready'));
  await page.getByRole('button', { name: 'Compact', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('main')?.classList.contains('compact'));
  const bufferingCurrent = page.locator('.queue-current');
  assert.ok(await bufferingCurrent.getByRole('button', { name: '停止播放', exact: true }).isEnabled());
  assert.equal(await bufferingCurrent.getByRole('button', { name: 'Remove', exact: true }).count(), 0);
  await page.getByRole('button', { name: 'Full', exact: true }).click();
  await page.evaluate(() => { window.__speechMockBuffering = false; });

  await page.evaluate(() => { window.__speechMockReject = true; });
  await page.evaluate(() => { window.__speechMockQueueError = true; });
  await composer.fill('keep this text when rejected');
  await page.getByRole('button', { name: 'Speak', exact: true }).click();
  await page.getByRole('alert').filter({ hasText: 'MOCK_REJECT' }).first().waitFor();
  assert.equal(await composer.inputValue(), 'keep this text when rejected');
  await page.waitForFunction(() => document.querySelector('.queue-history')?.textContent?.includes('TTS_FAILED: mock backend failure'));
  await page.getByRole('button', { name: 'Compact', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('main')?.classList.contains('compact'));
  assert.ok(await page.locator('.queue-pending').isVisible());
  for (const name of ['Speak Now', 'Move Up', 'Move Down', 'Remove']) {
    assert.ok(await page.getByRole('button', { name, exact: true }).isVisible(), `Compact queue action ${name} should be visible`);
  }
  assert.ok((await page.locator('.queue-history').textContent()).includes('TTS_FAILED: mock backend failure'));
  await page.evaluate(() => { window.__speechMockReject = false; });

  await page.getByRole('button', { name: 'Mini', exact: true }).click();
  await page.getByRole('button', { name: '開啟 TTS Quick Input' }).click();
  const quick = page.getByLabel('Compact quick input');
  await quick.fill('quick accepted text');
  await page.getByRole('button', { name: 'Speak', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('[data-testid="speech-quick-popup"]') === null);
  assert.deepEqual(diagnostics.errors, []);
  assert.deepEqual(diagnostics.network, []);
  await page.screenshot({ path: new URL('manual-tts-mock-mini.png', artifactDir).pathname.replace(/^\/(\w:)/, '$1') });
  const actions = await page.evaluate(() => window.__speechMockActions);
  await writeFile(new URL('manual-tts-mock-actions.json', artifactDir), JSON.stringify(actions, null, 2));
  await page.getByRole('button', { name: '展開 Compact', exact: true }).click();
  await page.getByRole('button', { name: 'Full', exact: true }).click();
  await page.setViewportSize({ width: 1040, height: 740 });
  await page.getByLabel('Mode', { exact: true }).selectOption('streaming_vc');
  await page.getByLabel('Engine', { exact: true }).selectOption('rvc');
  assert.equal(await page.getByLabel('Reference WAV').count(), 0);
  assert.equal(await page.getByLabel('RVC model_id').inputValue(), 'Sage_CN_HeroicFemale');
  assert.equal(await page.getByLabel('RVC f0_method').inputValue(), 'fcpe');
  assert.equal(await page.getByLabel('RVC source_mode').inputValue(), 'microphone');
  assert.ok(await page.getByRole('button', { name: '▶ START', exact: true }).isEnabled());
  await page.getByLabel('RVC model_id').selectOption('Wukong_HeroicMale');
  await page.getByLabel('RVC source_mode').selectOption('file');
  assert.ok(await page.getByLabel('Source WAV').isVisible());
  assert.equal(await page.getByLabel('Input device').count(), 0);
  await page.getByLabel('RVC pitch').fill('3');
  await page.getByLabel('自己監聽', { exact: true }).check();
  await page.getByRole('button', { name: '▶ START', exact: true }).click();
  await page.waitForFunction(() => window.__rvcMockStarts.length === 1);
  const rvcRequest = await page.evaluate(() => window.__rvcMockStarts[0]);
  assert.equal(rvcRequest.engine, 'rvc');
  assert.equal(rvcRequest.request.parameters.model_id, 'Wukong_HeroicMale');
  assert.equal(rvcRequest.request.parameters.source_mode, 'file');
  assert.equal(rvcRequest.request.parameters.pitch, 3);
  assert.equal(rvcRequest.request.monitor.enabled, true);
  assert.equal(rvcRequest.request.output, 'CABLE Input (VB-Audio Virtual Cable)');
  assert.ok(await page.getByLabel('RVC model_id').isDisabled());
  await page.getByRole('button', { name: '■ STOP', exact: true }).click();
  assert.ok(await page.getByLabel('RVC model_id').isEnabled());
  await mkdir(new URL('../../output/playwright/', import.meta.url), { recursive: true });
  await page.screenshot({ path: new URL('../../output/playwright/rvc-controls-mock.png', import.meta.url).pathname.replace(/^\/(\w:)/, '$1') });
  assert.deepEqual(diagnostics.errors, []);
  assert.deepEqual(diagnostics.network, []);
  await browser.close();
  return { status: 'PASS', consoleErrors: diagnostics.errors, networkErrors: diagnostics.network, actionCount: actions.length, rvc: 'model/source/F0/pitch/monitor/start/stop payload PASS' };
}

const report = { status: 'PASS', preview: await previewPass(), mock: await mockPass(), note: 'Mock IPC validates DOM/request/rejection behavior only; it is not native TTS or audio evidence.' };
await writeFile(new URL('manual-tts-report.json', artifactDir), JSON.stringify(report, null, 2));
console.log('PASS: manual TTS preview + explicit mock IPC UI checks; report in artifacts/desktop/ui/manual-tts-report.json');
