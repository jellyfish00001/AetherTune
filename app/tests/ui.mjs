import { uiText, setUiLocale } from './ui-text.mjs';
// 可重跑的 DOM／渲染檢核。CDP 模式連到真正 WebView2，預覽模式明確禁止 backend。
import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
const dir=new URL('../../artifacts/desktop/ui/',import.meta.url);await mkdir(dir,{recursive:true});
const native=!!process.env.AETHERTUNE_CDP;
const browser=native?await chromium.connectOverCDP(process.env.AETHERTUNE_CDP):await chromium.launch({channel:'msedge',headless:true});
const page=native?browser.contexts()[0].pages().find(p=>/tauri.localhost|127.0.0.1:1420/.test(p.url())):await browser.newPage({viewport:{width:1040,height:740}});
assert.ok(page,'找不到本機 AetherTune WebView');
const errors=[],network=[];
page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});page.on('requestfailed',r=>network.push({url:r.url(),failure:r.failure()}));
if(!native)await page.goto('http://127.0.0.1:1420/');
await page.waitForSelector('main');
setUiLocale(await page.locator('html').getAttribute('lang'));
assert.equal(await page.locator('main').getAttribute('data-native'),String(native));
const invoke=(name,args)=>page.evaluate(({name,args})=>window.__TAURI_INTERNALS__.invoke(name,args),{name,args});
const results=[];
// CDP mouse 座標相對 WebView；視窗移動後需換算，才能模擬固定螢幕上的游標軌跡。
// 若直接以 steps 移動 client 座標，screenX/Y 會累加視窗本身的位移，造成假的拖曳失敗。
async function dragNativeWindow(origin, {locked=false}={}) {
  const start={x:90,y:24}, delta={x:40,y:20};
  async function pointAt(fraction) {
    const current=await invoke('window_status');
    await page.mouse.move(
      start.x+delta.x*fraction-(current.position.x-origin.position.x)/origin.scale_factor,
      start.y+delta.y*fraction-(current.position.y-origin.position.y)/origin.scale_factor,
    );
  }
  await pointAt(0);await page.mouse.down();
  try {
    for(let step=1;step<=8;step++) {
      await pointAt(step/8);
      const expected={
        x:origin.position.x+(locked?0:delta.x*step/8*origin.scale_factor),
        y:origin.position.y+(locked?0:delta.y*step/8*origin.scale_factor),
      };
      let current;
      for(let attempt=0;attempt<30;attempt++) {
        current=await invoke('window_status');
        if(Math.abs(current.position.x-expected.x)<=2&&Math.abs(current.position.y-expected.y)<=2)break;
        await new Promise(resolve=>setTimeout(resolve,50));
      }
      assert.ok(Math.abs(current.position.x-expected.x)<=2&&Math.abs(current.position.y-expected.y)<=2,
        `native drag step ${step}: actual=${JSON.stringify(current.position)} expected=${JSON.stringify(expected)}`);
    }
  } finally {
    // mouse.up 也使用最後一個 client 座標；釋放前同步位置，避免額外產生一次位移。
    await pointAt(1);await page.mouse.up();
  }
}
if(native){const s=await invoke('shell_status');await invoke('set_shell',{shell:{...s,mode:'full',click_through:false}});await page.waitForFunction(()=>document.querySelector('main').classList.contains('full'));}
for(const mode of ['full','compact','mini']){
  if(mode!=='full')await page.getByTestId(`window-mode-${mode}`).click();
  await page.waitForFunction(mode=>document.querySelector('main').classList.contains(mode),mode);
  if(!native)await page.setViewportSize({width:mode==='full'?1040:420,height:mode==='full'?740:mode==='compact'?490:74});
  const actual=native?await invoke('window_status'):await page.evaluate(()=>({size:{width:innerWidth,height:innerHeight}}));
  if(native){assert.equal(actual.decorated,false);assert.equal(actual.always_on_top,mode!=='full');assert.equal(actual.tray_registered,true);assert.equal(Math.round(actual.size.width/actual.scale_factor),mode==='full'?1040:420);}
  await page.screenshot({path:new URL(`${native?'native':'preview'}-${mode}.png`,dir).pathname.replace(/^\/(\w:)/,'$1')});
  results.push({mode,actual});
}
await page.getByRole('button',{name: uiText('展開 Compact')}).click();
await page.getByRole('button',{name: uiText('Full'),exact:true}).click();
if(!native)await page.setViewportSize({width:1040,height:740});
await page.getByTestId('control:Mode').selectOption('speech_reconstruction');
assert.deepEqual(await page.getByTestId('control:Engine').locator('option').allTextContents(),['CosyVoice','Breeze TTS 2']);
assert.equal(await page.getByRole('button',{name: uiText('▶ START'),exact:true}).count(),0);
await page.getByTestId('control:Mode').selectOption('text_to_speech');
assert.deepEqual(await page.getByTestId('control:Engine').locator('option').allTextContents(),['CosyVoice','Breeze TTS 2']);
await page.getByTestId('control:Mode').selectOption('streaming_vc');
for(const engine of ['seed-vc','meanvc2','xvc']){
  await page.getByTestId('control:Engine').selectOption(engine);
  const startRect=await page.getByRole('button',{name: uiText('▶ START'),exact:true}).boundingBox();
  const viewportHeight=await page.evaluate(()=>innerHeight);
  assert.ok(startRect&&startRect.y>=0&&startRect.y+startRect.height<=viewportHeight,`${engine} START 位於首屏`);
  assert.equal(await page.getByTestId('control:Host API').count(),1,`${engine} route host API`);
  assert.equal(await page.getByTestId('control:Input device').count(),1,`${engine} route input`);
  assert.equal(await page.getByTestId('control:Output device').count(),1,`${engine} route output`);
  assert.equal(await page.getByTestId('control:自己監聽').count(),1,`${engine} shared monitor`);
  assert.equal(await page.getByRole('button',{name: uiText('調整音效'),exact:true}).count(),1,`${engine} effects settings entry`);
  assert.equal(await page.getByTestId('control:Reference WAV').count(),1,`${engine} reference`);
  assert.equal(await page.getByTestId('control:Source WAV').count(),0,`${engine} has no source WAV`);
  if(!native)assert.equal(await page.getByRole('button',{name: uiText('▶ START'),exact:true}).isEnabled(),false);
}
await page.getByTestId('control:Engine').selectOption('rvc');
assert.equal(await page.getByTestId('control:RVC model_id').inputValue(),'Sage_CN_HeroicFemale');
assert.equal(await page.getByTestId('control:Reference WAV').count(),0);
assert.equal(await page.getByTestId('control:自己監聽').count(),1);
assert.equal(await page.getByRole('button',{name: uiText('調整音效'),exact:true}).count(),1);
await page.getByTestId('control:RVC source_mode').selectOption('microphone');
assert.equal(await page.getByTestId('control:Source WAV').count(),0);
await page.getByTestId('control:RVC source_mode').selectOption('file');
assert.equal(await page.getByTestId('control:Source WAV').count(),1);
assert.equal(await page.getByTestId('control:Input device').count(),0);
await page.getByRole('button',{name: uiText('Mini'),exact:true}).click();
await page.waitForFunction(()=>document.querySelector('main').classList.contains('mini'));
assert.equal(await page.getByText('WAV',{exact:true}).count(),1,'RVC File 的 Mini 不得誤顯示 Mic');
assert.equal(await page.getByRole('button',{name: uiText('開啟 TTS Quick Input'),exact:true}).count(),0,'變聲 Mini 不顯示無作用的文字輸入按鈕');
await page.getByRole('button',{name: uiText('展開 Compact')}).click();
await page.getByRole('button',{name: uiText('Full'),exact:true}).click();
await page.waitForFunction(()=>document.querySelector('main').classList.contains('full'));
if(!native)await page.setViewportSize({width:1040,height:740});
if(!native)assert.equal(await page.getByRole('button',{name: uiText('▶ START'),exact:true}).isEnabled(),false);
await page.getByTestId('control:Engine').selectOption('seed-vc');
assert.equal(await page.getByTestId('control:Source WAV').count(),0);
if(!native)assert.equal(await page.getByRole('button',{name: uiText('▶ START'),exact:true}).isEnabled(),false);
const storedVcSettings=await page.evaluate(()=>JSON.parse(localStorage.getItem('aethertune.vc-settings.v1')||'null'));
assert.ok(storedVcSettings?.route&&storedVcSettings?.monitor&&storedVcSettings?.rvcParameters);
const storedEffects=await page.evaluate(()=>JSON.parse(localStorage.getItem('aethertune.audio-effects.v1')||'null'));
assert.equal(Object.keys(storedEffects).length,6);
assert.equal(storedVcSettings.metrics,undefined);
if(native){
  let shell=await invoke('shell_status');
  await invoke('set_shell',{shell:{...shell,mode:'compact',locked:false,click_through:false}});
  await page.waitForFunction(()=>document.querySelector('main').classList.contains('compact'));
  // 可見 WebView 移窗時，Windows 會以實體游標位置送出 buttons=0 的 pointermove，
  // 使 CDP 按住中的 pointer capture 遺失。先隔離兩種輸入來源，再驗 CDP 位移；
  // 不放寬位移／鎖定斷言。前面的三版面仍記錄實際 visible，真實拖曳另由 Computer Use 驗收。
  const visibleBeforeDrag=(await invoke('window_status')).visible;
  await invoke('hide');
  assert.equal((await invoke('window_status')).visible,false,'CDP 拖曳需隔離實體滑鼠事件');
  results.push({assertion:'CDP drag input isolation',visibleBefore:visibleBeforeDrag,visibleDuring:false});
  const dragOrigin=await invoke('window_status');
  await dragNativeWindow(dragOrigin);
  // invoke 是非同步：以 Node polling 等待位置，不能用 async waitForFunction 的 Promise truthiness。
  let moved;for(let n=0;n<30;n++){moved=await invoke('window_status');if(moved.position.x!==dragOrigin.position.x)break;await new Promise(r=>setTimeout(r,100));}
  assert.ok(Math.abs(moved.position.x-dragOrigin.position.x-40*dragOrigin.scale_factor)<=2);
  assert.ok(Math.abs(moved.position.y-dragOrigin.position.y-20*dragOrigin.scale_factor)<=2);
  results.push({assertion:'native drag',before:dragOrigin.position,after:moved.position});
  await invoke('set_shell',{shell:{...shell,mode:'compact',locked:true,click_through:false}});
  await dragNativeWindow(moved,{locked:true});
  assert.deepEqual((await invoke('window_status')).position,moved.position);
  results.push({assertion:'Lock Position prevents drag',position:moved.position});
  await invoke('set_shell',{shell:{...shell,mode:'compact',locked:false,click_through:false}});
  await invoke('set_shell',{shell:{...shell,mode:'compact',click_through:true}});
  assert.equal((await invoke('window_status')).native_click_through,true);
  await invoke('set_shell',{shell:{...shell,mode:'compact',click_through:false}});
  assert.equal((await invoke('window_status')).native_click_through,false);
  await invoke('hide');assert.equal((await invoke('window_status')).visible,false);
  // 此測試在 UI hide 後只核對原生 flag；Tray／hotkey 實際點擊另由 Computer Use 複核。
  await invoke('set_shell',{shell:{...shell,mode:'full',click_through:false}});
}
assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
await writeFile(new URL(`${native?'native':'preview'}-report.json`,dir),JSON.stringify({status:'PASS',surface:native?'Tauri WebView2 CDP':'Playwright Edge preview',url:page.url(),results,assertions:['3 modes + native dimensions','mode capability filtering','all streaming VC routes + shared monitor/Post-FX controls','RVC source mode only','no fake audio metrics',...(native?['frameless/topmost/tray registered','native click-through flag on/off','hide native window']:['preview start disabled'])],consoleErrors:errors,networkErrors:network},null,2));
await browser.close();console.log(`PASS: ${native?'native WebView2':'browser preview'} UI; screenshots/report in artifacts/desktop/ui`);
