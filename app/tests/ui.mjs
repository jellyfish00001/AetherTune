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
assert.equal(await page.locator('main').getAttribute('data-native'),String(native));
const invoke=(name,args)=>page.evaluate(({name,args})=>window.__TAURI_INTERNALS__.invoke(name,args),{name,args});
const results=[];
if(native){const s=await invoke('shell_status');await invoke('set_shell',{shell:{...s,mode:'full',click_through:false}});await page.waitForFunction(()=>document.querySelector('main').classList.contains('full'));}
for(const mode of ['full','compact','mini']){
  if(mode!=='full')await page.getByRole('button',{name:mode==='compact'?'Compact':'Mini',exact:true}).click();
  await page.waitForFunction(mode=>document.querySelector('main').classList.contains(mode),mode);
  if(!native)await page.setViewportSize({width:mode==='full'?1040:420,height:mode==='full'?740:mode==='compact'?490:74});
  const actual=native?await invoke('window_status'):await page.evaluate(()=>({size:{width:innerWidth,height:innerHeight}}));
  if(native){assert.equal(actual.decorated,false);assert.equal(actual.always_on_top,mode!=='full');assert.equal(actual.tray_registered,true);assert.equal(Math.round(actual.size.width/actual.scale_factor),mode==='full'?1040:420);}
  await page.screenshot({path:new URL(`${native?'native':'preview'}-${mode}.png`,dir).pathname.replace(/^\/(\w:)/,'$1')});
  results.push({mode,actual});
}
await page.getByRole('button',{name:'展開 Compact'}).click();
await page.getByRole('button',{name:'Full',exact:true}).click();
if(!native)await page.setViewportSize({width:1040,height:740});
await page.getByLabel('Mode',{exact:true}).selectOption('speech_reconstruction');
assert.deepEqual(await page.getByLabel('Engine',{exact:true}).locator('option').allTextContents(),['CosyVoice','Breeze TTS 2']);
assert.equal(await page.getByRole('button',{name:'▶ START',exact:true}).isEnabled(),false);
await page.getByLabel('Mode',{exact:true}).selectOption('text_to_speech');
assert.deepEqual(await page.getByLabel('Engine',{exact:true}).locator('option').allTextContents(),['CosyVoice','Breeze TTS 2']);
await page.getByLabel('Mode',{exact:true}).selectOption('streaming_vc');
await page.getByLabel('Engine',{exact:true}).selectOption('meanvc2');
assert.ok(await page.getByLabel('Source WAV',{exact:true}).isVisible());
await page.getByLabel('Engine',{exact:true}).selectOption('rvc');
assert.equal(await page.getByRole('button',{name:'▶ START',exact:true}).isEnabled(),false);
await page.getByLabel('Engine',{exact:true}).selectOption('seed-vc');
if(!native)assert.equal(await page.getByRole('button',{name:'▶ START',exact:true}).isEnabled(),false);
if(native){
  let shell=await invoke('shell_status');
  await invoke('set_shell',{shell:{...shell,mode:'compact',locked:false,click_through:false}});
  await page.waitForFunction(()=>document.querySelector('main').classList.contains('compact'));
  const dragOrigin=await invoke('window_status');
  await page.mouse.move(90,24);await page.mouse.down();await page.mouse.move(130,44,{steps:8});await page.mouse.up();
  // invoke 是非同步：以 Node polling 等待位置，不能用 async waitForFunction 的 Promise truthiness。
  let moved;for(let n=0;n<30;n++){moved=await invoke('window_status');if(moved.position.x!==dragOrigin.position.x)break;await new Promise(r=>setTimeout(r,100));}
  assert.ok(Math.abs(moved.position.x-dragOrigin.position.x-40*dragOrigin.scale_factor)<=2);
  results.push({assertion:'native drag',before:dragOrigin.position,after:moved.position});
  await invoke('set_shell',{shell:{...shell,mode:'compact',locked:true,click_through:false}});
  await page.mouse.move(90,24);await page.mouse.down();await page.mouse.move(130,44,{steps:8});await page.mouse.up();
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
await writeFile(new URL(`${native?'native':'preview'}-report.json`,dir),JSON.stringify({status:'PASS',surface:native?'Tauri WebView2 CDP':'Playwright Edge preview',url:page.url(),results,assertions:['3 modes + native dimensions','mode capability filtering','planned engines disabled','no fake audio metrics',...(native?['frameless/topmost/tray registered','native click-through flag on/off','hide native window']:['preview start disabled'])],consoleErrors:errors,networkErrors:network},null,2));
await browser.close();console.log(`PASS: ${native?'native WebView2':'browser preview'} UI; screenshots/report in artifacts/desktop/ui`);
