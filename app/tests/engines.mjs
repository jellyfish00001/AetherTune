// 真正 Desktop UI 的三個 migration Adapter 啟停；不開麥克風 stream、不作 audio PASS。
import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
const dir=new URL('../../artifacts/desktop/integration/',import.meta.url);await mkdir(dir,{recursive:true});
await writeFile(new URL('engines-report.json',dir),JSON.stringify({status:'RUNNING',audio_status:'WAITING',note:'此 run 未完成前不得沿用舊 PASS'}));
const browser=await chromium.connectOverCDP(process.env.AETHERTUNE_CDP??'http://127.0.0.1:9223');
const page=browser.contexts()[0].pages().find(p=>/tauri.localhost|127.0.0.1:1420/.test(p.url()));
assert.ok(page);
const invoke=(name,args)=>page.evaluate(({name,args})=>window.__TAURI_INTERNALS__.invoke(name,args),{name,args});
async function wait(predicate,timeout=30000){const until=Date.now()+timeout;while(Date.now()<until){if(await predicate())return;await new Promise(r=>setTimeout(r,100));}throw new Error('runtime assertion timeout');}
await invoke('stop');const shell=await invoke('shell_status');await invoke('set_shell',{shell:{...shell,mode:'full',click_through:false}});
const results=[];
for(const engine of ['seed-vc','meanvc2','xvc']){
  await page.getByLabel('Mode',{exact:true}).selectOption('streaming_vc');
  await page.getByLabel('Engine',{exact:true}).selectOption(engine);
  if(engine==='seed-vc')await page.getByLabel('Input',{exact:true}).fill('麥克風 (HyperX QuadCast S)');
  await page.getByRole('button',{name:'檢查啟動條件',exact:true}).click();
  const preflight=await invoke('validate',{engine,request:{source:'D:/AetherTune/dataset/reference-voices/voice-male-m1.wav',reference:'D:/AetherTune/dataset/reference-voices/voice-female-f1.wav',input:'麥克風 (HyperX QuadCast S)',output:'CABLE Input (VB-Audio Virtual Cable)',host_api:'Windows DirectSound',parameters:{}}});
  await page.getByRole('status').filter({hasText:preflight.valid?'預檢 PASS':'預檢 BLOCKED'}).waitFor();
  const before=0; // EngineManager 在每次新 run 清空有限的 UI log ring；完整 log 留 disk。
  await page.getByRole('button',{name:'▶ START',exact:true}).click();
  await wait(async()=>Number.isInteger((await invoke('status')).runner_pid)||(await invoke('status')).value==='ERROR');
  const runnerPid=(await invoke('status')).runner_pid;
  // 等到本次 runner 回報訊息或完成，以證明不是只起了空白橋接程序。
  await wait(async()=>(await invoke('status')).value==='ERROR'||(await invoke('logs')).slice(before).some(e=>e.type==='log'&&e.stream==='backend'),120000);
  if(engine==='seed-vc'&&preflight.valid)await wait(async()=>{const s=await invoke('status');return s.value==='ERROR'||(await invoke('logs')).some(e=>e.type==='log'&&String(e.message).includes('Official GUI opens'));});
  const preStop=await invoke('status');
  const events=(await invoke('logs')).slice(before);
  if(preflight.valid)assert.ok(events.some(e=>e.type==='log'&&e.stream==='backend'));
  else assert.equal(preStop.value,'ERROR');
  assert.ok(!events.some(e=>e.type==='state'&&e.audio_verified===true));
  const pid=runnerPid;
  await page.getByRole('button',{name:'■ STOP',exact:true}).click();
  await wait(async()=>{const s=await invoke('status');return s.value==='OFFLINE'&&!s.service_alive;});
  results.push({engine,status:'PASS',scope:preflight.valid?'runner spawn/stop':'blocked preflight -> ERROR -> stop',upstream_startup:preStop.value==='ERROR'?'BLOCKED':'WAITING',adapter:engine==='seed-vc'?'TEMPORARY GUI':'WAV runner',preflight,pid,preStop,postStop:await invoke('status'),events});
}
// 缺 reference 的負向路徑，UI 必須顯示 ERROR 並能重新 Start。
const request={source:'D:/AetherTune/dataset/reference-voices/voice-male-m1.wav',reference:'D:/AetherTune/does-not-exist.wav',parameters:{}};
await invoke('start',{engine:'meanvc2',request});
await wait(async()=>(await invoke('status')).value==='ERROR');
assert.equal((await invoke('status')).audio_verified,false);
await invoke('stop');
await writeFile(new URL('engines-report.json',dir),JSON.stringify({status:'PARTIAL',control_status:'PASS',audio_status:'WAITING',results,negative:['missing reference -> ERROR -> stop'],inputs:['voice-male-m1.wav','voice-female-f1.wav'].map(name=>({path:`dataset/reference-voices/${name}`,sha256:createHash('sha256').update(readFileSync(`D:/AetherTune/dataset/reference-voices/${name}`)).digest('hex')}))},null,2));
await browser.close();console.log('Control assertions PASS; inspect per-engine BLOCKED/WAITING. Audio WAITING. Run cleanup.ps1 for OS process proof.');
