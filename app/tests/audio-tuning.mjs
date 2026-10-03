// 真實 DOM、preview IPC mock 與原生 WebView2 設定檢核；不將 mock 升格音訊證據。
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
const native = !!process.env.AETHERTUNE_CDP;
const directory = new URL('../../artifacts/desktop/audio-tuning-20261003/ui/', import.meta.url);
await mkdir(directory, { recursive: true });
const manifests = await Promise.all(['seed-vc','meanvc2','xvc','rvc','cosyvoice','breeze'].map(async id => JSON.parse(await readFile(new URL(`../../contracts/engines/${id}.json`, import.meta.url), 'utf8'))));
const browser = native ? await chromium.connectOverCDP(process.env.AETHERTUNE_CDP) : await chromium.launch({ channel: 'msedge', headless: true });
const page = native ? browser.contexts()[0].pages().find(p => /tauri.localhost/.test(p.url())) : await browser.newPage({ viewport: { width: 1040, height: 740 } });
const errors = [], network = [], checks = [];
page.on('pageerror', e => errors.push(e.message));
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
page.on('requestfailed', r => network.push(r.url()));
const invoke = (name, args) => page.evaluate(({name,args}) => window.__TAURI_INTERNALS__.invoke(name,args), {name,args});
const keys = ['aethertune.vc-settings.v1','aethertune.ui-language.v1','aethertune.audio-effects.v1'];
let original, shell;
if (native) {
  const state = await invoke('status'), speech = await invoke('speech_status');
  assert.equal(state.service_alive, false); assert.ok(['IDLE','ERROR'].includes(speech.state));
  original = await page.evaluate(keys => Object.fromEntries(keys.map(k => [k,localStorage.getItem(k)])), keys);
  shell = await invoke('shell_status');
} else {
  await page.addInitScript(({manifests}) => {
    Object.defineProperty(window,'isTauri',{value:true});
    if (!sessionStorage.getItem('tuning-seeded')) {
      localStorage.setItem('aethertune.vc-settings.v1', JSON.stringify({rvcParameters:{pitch:-2,index_rate:.5},route:{input:'Mic',output:'CABLE Input',host_api:'WASAPI'}}));
      sessionStorage.setItem('tuning-seeded','1');
    }
    let shell = {mode:'full',opacity:1,always_on_top:false,locked:false,click_through:false,visibility_hotkey:'Ctrl+Alt+A',voice_hotkey:'Ctrl+Alt+V',quick_input:false};
    window.__vcStatus = {value:'OFFLINE',engine_id:null,audio_verified:false,reason:'mock',service_alive:false}; window.__starts = [];
    const devices = {inputs:[{name:'Mic',host_api:'WASAPI',selectable:true,channels:1,is_default:true}],outputs:[{name:'CABLE Input',host_api:'WASAPI',selectable:true,channels:2,is_default:true}]};
    const speech = {state:'IDLE',queue:[],readiness:{},profiles:[],session_id:'mock',current_request_id:null,settings:{engine_id:'cosyvoice',voice_profile_id:'reference-male',enter_to_send:true}};
    window.__TAURI_INTERNALS__ = {invoke:async (name,args={}) => {
      if(name==='discover') return manifests;
      if(name==='status') return window.__vcStatus;
      if(name==='logs') return [];
      if(name==='shell_status') return shell;
      if(name==='set_shell') {shell=args.shell;return null;}
      if(name==='speech_status') return window.__speechProgressStatus ?? speech;
      if(name==='speech_action') return {accepted:true,result:args.action?.action==='audio_devices'?devices:{}};
      if(name==='start') {window.__starts.push(args);window.__vcStatus={...window.__vcStatus,value:'LOADING',engine_id:args.engine,service_alive:true,progress:{phase:'model_load',elapsed_seconds:200,last_progress_seconds_ago:190,observed_at:new Date().toISOString(),worker_alive:true}};return window.__vcStatus;}
      if(name==='stop') {window.__vcStatus={...window.__vcStatus,value:'OFFLINE',service_alive:false,progress:undefined};return window.__vcStatus;}
      return null;
    },transformCallback:()=>1,unregisterCallback:()=>{},runCallback:()=>{}};
    window.__TAURI_EVENT_PLUGIN_INTERNALS__={unregisterListener:()=>{}};
  }, {manifests});
  await page.goto('http://127.0.0.1:1420/');
}
try {
  await page.evaluate(() => localStorage.setItem('aethertune.ui-language.v1','zh-TW'));
  if(native) await invoke('set_shell',{shell:{...shell,mode:'full',quick_input:false,click_through:false}});
  await page.reload(); await page.getByTestId('nav-LIVE').click();
  const engine = page.getByTestId('control:Engine');
  await engine.selectOption('rvc');
  const pitch=page.getByTestId('control:RVC pitch');
  if(!native) assert.equal(await pitch.inputValue(),'-2');
  await pitch.fill('-3'); await pitch.press('ArrowUp'); assert.equal(await pitch.inputValue(),'-2');
  await pitch.locator('..').locator('.number-buttons button').first().click(); assert.equal(await pitch.inputValue(),'-1');
  await pitch.fill('-99'); await pitch.blur(); assert.equal(await pitch.inputValue(),'-24');
  await pitch.fill('-2'); await pitch.blur();
  checks.push(`${native?'restored RVC record':'legacy RVC migration'} / negative / keys / dark buttons / clamps`);
  for (const id of ['rvc','seed-vc','xvc','meanvc2']) {
    await engine.selectOption(id);
    if(!native && id!=='rvc') await page.getByTestId('control:Reference WAV').fill('fixture.wav');
    const manifest=manifests.find(m=>m.id===id);
    if(manifest.parameters.some(p=>p.level==='advanced')) {
      const details=page.locator('.engine-parameters details');
      assert.equal(await details.getAttribute('open'),null); await details.locator('summary').click();
    }
    for(const p of manifest.parameters) assert.equal(await page.getByTestId(`control:${id==='rvc'?'RVC':`VC ${id}`} ${p.name}`).count(),1);
    if(id==='meanvc2') await page.getByTestId('control:VC meanvc2 model').selectOption('120ms');
    if(id==='seed-vc') {
      await page.getByTestId('control:VC seed-vc diffusion_steps').fill('6'); await page.getByTestId('control:VC seed-vc diffusion_steps').blur();
      await page.getByTestId('control:VC seed-vc block_time').fill('0.04'); await page.getByTestId('control:VC seed-vc block_time').blur();
      await page.getByTestId('control:VC seed-vc crossfade_length').fill('0.06'); await page.getByTestId('control:VC seed-vc crossfade_length').blur();
      assert.equal(await page.getByRole('button',{name:'▶ 開始',exact:true}).isEnabled(),false);
      await page.getByTestId('control:VC seed-vc block_time').fill('0.3'); await page.getByTestId('control:VC seed-vc block_time').blur();
      await page.getByTestId('control:VC seed-vc crossfade_length').fill('0.04'); await page.getByTestId('control:VC seed-vc crossfade_length').blur();
    }
    if(id==='xvc') {
      await page.getByTestId('control:VC xvc current').fill('161'); await page.getByTestId('control:VC xvc current').blur();
      assert.equal(await page.getByRole('button',{name:'▶ 開始',exact:true}).isEnabled(),false);
      await page.getByTestId('control:VC xvc current').fill('240'); await page.getByTestId('control:VC xvc current').blur();
    }
    await page.getByTestId('nav-SETTINGS').click();
    await page.getByTestId('control:音效引擎').selectOption(id);
    await page.getByTestId('control:啟用輸入降噪').check();
    await page.getByTestId('control:降噪強度').fill(id==='rvc'?'15':'12'); await page.getByTestId('control:降噪強度').blur();
    await page.getByTestId('control:Post-FX wet').fill('0'); await page.getByTestId('control:Post-FX wet').blur();
    await page.getByTestId('nav-LIVE').click();
    if(!native) {
      assert.equal(await page.getByRole('button',{name:'▶ 開始',exact:true}).isEnabled(),true,`route ready: ${id} ${JSON.stringify(await page.locator('.vc-audio-controls select').evaluateAll(nodes=>nodes.map(n=>({label:n.getAttribute('aria-label'),value:n.value,options:[...n.options].map(o=>o.value)}))))} ${await page.locator('main').innerText()}`);
      await page.getByRole('button',{name:'▶ 開始',exact:true}).click();
      await page.getByTestId('load-status').getByText('載入較久，尚未判定失敗；可停止或查看診斷資料。',{exact:true}).waitFor();
      assert.equal(await page.locator('.engine-parameters input:enabled').count(),0);
      const request=await page.evaluate(()=>window.__starts.at(-1).request);
      assert.equal(request.noise_reduction.enabled,true); assert.equal(request.postfx.wet,0);
      assert.deepEqual(request.parameters, await page.evaluate(id=>JSON.parse(localStorage.getItem('aethertune.vc-settings.v1')).engineParameters[id],id));
      await page.getByRole('button',{name:'■ 停止',exact:true}).click();
    }
  }
  checks.push(`four manifests / advanced collapsed / per-engine NR / FX wet independent${native?'':' / START payload and loading STOP'}`);
  await page.reload(); await page.getByTestId('nav-LIVE').click(); await page.getByTestId('control:Engine').selectOption('rvc');
  assert.equal(await page.getByTestId('control:RVC pitch').inputValue(),'-2');
  await page.getByTestId('nav-SETTINGS').click(); await page.getByTestId('control:音效引擎').selectOption('rvc');
  assert.equal(await page.getByTestId('control:降噪強度').inputValue(),'15');
  assert.equal(await page.locator('.audio-troubleshooting').getAttribute('open'),null);
  await page.locator('.audio-troubleshooting summary').click(); assert.equal(await page.locator('.audio-troubleshooting h3').count(),5);
  await page.locator('.audio-troubleshooting summary').click();
  for(const language of ['zh-TW','en']) {
    await page.getByTestId('ui-language').selectOption(language);
    for(const width of native ? [1040] : [1040,420]) {
      if(!native) await page.setViewportSize({width,height:740});
      const icon=page.locator('.audio-effects-settings .help-icon').nth(5);
      await page.getByTestId('control:Post-FX low').focus();
      await icon.focus(); await page.getByRole('tooltip').waitFor();
      const box=await page.getByRole('tooltip').boundingBox(), viewport=await page.evaluate(()=>({width:innerWidth,height:innerHeight}));
      assert.ok(box.x>=0&&box.y>=0&&box.x+box.width<=viewport.width&&box.y+box.height<=viewport.height);
      await page.screenshot({path:new URL(`${native?'native':'preview'}-${language}-${width}-tooltip.png`,directory).pathname.replace(/^\/(\w:)/,'$1')});
      await page.keyboard.press('Escape'); assert.equal(await page.getByRole('tooltip').count(),0);
      await icon.click(); await page.getByRole('tooltip').waitFor(); await page.keyboard.press('Escape');
    }
  }
  await page.getByTestId('control:音效引擎').selectOption('breeze'); assert.equal(await page.getByTestId('control:啟用輸入降噪').count(),0);
  checks.push('reload persistence / five symptoms / bilingual focus-click-Escape / popup bounds / no TTS NR');
  await page.getByTestId('nav-LIVE').click();
  await page.getByTestId('window-mode-compact').click();
  await page.locator('main.compact').waitFor();
  await page.screenshot({path:new URL(`${native?'native':'preview'}-compact.png`,directory).pathname.replace(/^\/(\w:)/,'$1')});
  await page.getByTestId('control:調整音效').click();
  await page.locator('main.full .audio-effects-settings').waitFor();
  checks.push('Compact effects entry restores Full settings');
  if(!native) {
    // 長時間載入後生成／播放仍各自計秒；Mini 在 Quick Input 關閉時也顯示目前階段。
    await page.getByTestId('ui-language').selectOption('zh-TW');
    await page.getByTestId('nav-LIVE').click();
    await page.getByTestId('control:Mode').selectOption('text_to_speech');
    await page.getByTestId('control:Engine').selectOption('cosyvoice');
    await page.evaluate(() => { window.__speechProgressStatus = {state:'GENERATING',queue:[{id:'warm-clock',session_id:'mock',engine_id:'cosyvoice',voice_profile_id:'reference-male',text:'clock test',source:'manual',status:'generating',priority:0,created_at:new Date().toISOString()}],current_request_id:'warm-clock',session_id:'mock',profiles:[],readiness:{},settings:{engine_id:'cosyvoice',voice_profile_id:'reference-male'},progress:{request_id:'warm-clock',phase:'generating',elapsed_seconds:300,last_progress_seconds_ago:7,observed_at:new Date().toISOString(),worker_alive:true,runtime_reused:true,load_seconds:0}}; });
    await page.getByText('模型已就緒（重用）',{exact:true}).waitFor();
    await page.getByTestId('window-mode-mini').click();
    await page.locator('.load-mini').filter({hasText:'生成語音'}).waitFor();
    assert.ok(Number((await page.locator('.load-mini').innerText()).match(/(\d+)s/)[1])<30);
    await page.evaluate(() => { window.__speechProgressStatus.state='PLAYING';window.__speechProgressStatus.progress={...window.__speechProgressStatus.progress,phase:'playing',elapsed_seconds:500,last_progress_seconds_ago:5,observed_at:new Date().toISOString()}; });
    await page.locator('.load-mini').filter({hasText:'播放'}).waitFor();
    assert.ok(Number((await page.locator('.load-mini').innerText()).match(/(\d+)s/)[1])<30);
    await page.screenshot({path:new URL('preview-mini-playing.png',directory).pathname.replace(/^\/(\w:)/,'$1')});
    checks.push('TTS model reuse / independent generation and playback clocks / Mini without Quick Input');
  }
  assert.deepEqual(errors,[]); assert.deepEqual(network,[]);
  await writeFile(new URL(`${native?'native':'preview'}-report.json`,directory),JSON.stringify({status:'PASS',surface:native?'WebView2':'Edge + explicit IPC mock',url:page.url(),viewport:await page.evaluate(()=>({width:innerWidth,height:innerHeight})),checks,consoleErrors:errors,networkErrors:network},null,2));
  console.log(`PASS: ${native?'WebView2':'Edge mock'} audio tuning and progress`);
} finally {
  if(native) {
    await page.evaluate(original=>{for(const [key,value] of Object.entries(original)) value===null?localStorage.removeItem(key):localStorage.setItem(key,value);},original);
    await invoke('set_shell',{shell}); await page.reload();
  }
  await browser.close();
}
