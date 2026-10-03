// 根目錄 exe 的真實取消、失敗與 cold/warm TTS；主輸出限定 CABLE，不判定人耳或 LIVE。
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir,readFile,writeFile } from 'node:fs/promises';
const dir=new URL('../../artifacts/desktop/audio-tuning-20261003/native-progress/',import.meta.url);
await mkdir(dir,{recursive:true});
const browser=await chromium.connectOverCDP(process.env.AETHERTUNE_CDP??'http://127.0.0.1:9222');
const page=browser.contexts()[0].pages().find(p=>/tauri.localhost/.test(p.url()));
const invoke=(name,args)=>page.evaluate(({name,args})=>window.__TAURI_INTERNALS__.invoke(name,args),{name,args});
const shell=await invoke('shell_status');
const original=await page.evaluate(()=>({local:{...localStorage},session:{...sessionStorage}}));
const errors=[],network=[],results=[],progress=[];
page.on('pageerror',e=>errors.push(e.message));
page.on('console',m=>{if(m.type()==='error') errors.push(m.text());});
page.on('requestfailed',r=>network.push(r.url()));
const pause=()=>new Promise(resolve=>setTimeout(resolve,250));
async function waitSnapshot(predicate,command='speech_status',timeout=300000) {
  const until=Date.now()+timeout;
  while(Date.now()<until) {
    const status=await invoke(command);
    if(status.progress) progress.push({...status.progress,state:status.state??status.value,engine:status.engine_id??status.queue?.find(q=>q.id===status.current_request_id)?.engine_id});
    if(predicate(status)) return status;
    await pause();
  }
  throw new Error(`Timeout ${command}: ${JSON.stringify(await invoke(command))}`);
}
try {
  assert.equal((await invoke('status')).service_alive,false);
  assert.equal((await invoke('speech_status')).current_request_id,null);
  await invoke('set_shell',{shell:{...shell,mode:'full',quick_input:false,click_through:false}});
  await page.evaluate(()=>localStorage.setItem('aethertune.ui-language.v1','zh-TW')); await page.reload();
  await page.getByTestId('nav-LIVE').click();
  await page.getByTestId('control:Mode').selectOption('streaming_vc');
  await page.getByTestId('control:Engine').selectOption('seed-vc');
  await page.getByTestId('control:Reference WAV').fill('D:\\AetherTune\\dataset\\reference-voices\\voice-female-f1.wav');
  await page.getByTestId('control:Host API').selectOption('Windows DirectSound');
  await page.getByTestId('control:Input device').selectOption('麥克風 (HyperX QuadCast S)');
  await page.getByTestId('control:Output device').selectOption('CABLE Input (VB-Audio Virtual Cable)');
  await page.getByTestId('control:自己監聽').uncheck();
  await page.getByRole('button',{name:'▶ 開始',exact:true}).click();
  const loading=await waitSnapshot(s=>s.value==='LOADING'&&s.progress?.worker_alive===true,'status',30000);
  await page.getByTestId('load-status').locator('.load-current').waitFor();
  await page.screenshot({path:new URL('vc-loading.png',dir).pathname.replace(/^\/(\w:)/,'$1')});
  await page.getByRole('button',{name:'■ 停止',exact:true}).click();
  const stopped=await waitSnapshot(s=>s.value==='OFFLINE'&&!s.service_alive,'status',20000);
  assert.equal(stopped.progress,undefined);
  const log=await invoke('logs'); results.push({check:'VC load cancel',loading,stopped,log});
  // 後端拒絕非法 NR；不等到載入模型才報錯。
  await invoke('start',{engine:'seed-vc',request:{reference:'D:\\AetherTune\\dataset\\reference-voices\\voice-female-f1.wav',input:'麥克風 (HyperX QuadCast S)',output:'CABLE Input (VB-Audio Virtual Cable)',host_api:'Windows DirectSound',parameters:{},noise_reduction:{enabled:true,strength_db:25}}});
  const failed=await waitSnapshot(s=>s.value==='ERROR','status',30000);
  assert.equal(failed.progress.phase,'error'); assert.equal(failed.progress.worker_alive,false);
  results.push({check:'Illegal NR rejected',failed}); await invoke('stop');
  await page.getByTestId('control:Mode').selectOption('text_to_speech');
  for(const engine of ['cosyvoice','breeze']) {
    await page.getByTestId('control:Engine').selectOption(engine);
    for(let index=0;index<2;index++) {
      const profile=engine==='cosyvoice'?'official-cosyvoice-sample':'reference-mandarin-female';
      const ack=await invoke('speech_action',{action:{action:'submit',request:{engine_id:engine,voice_profile_id:profile,text:index?'模型已就緒，這是第二句。':'這是載入與介面測試。我們需要確認模型載入、語音生成、音訊播放，以及迷你視窗中的等待時間都能正確顯示。請依目前階段判斷是否繼續等待。',source:'manual',metadata:{route:{output:'CABLE Input (VB-Audio Virtual Cable)',host_api:'Windows DirectSound',monitor:{enabled:false}},postfx:{enabled:false}}}}});
      assert.equal(ack.accepted,true,JSON.stringify(ack)); const requestId=ack.result.request_id;
      const generating=await waitSnapshot(s=>s.current_request_id===requestId&&s.progress?.phase==='generating');
      assert.equal(generating.progress.runtime_reused,index===1);
      assert.equal(generating.progress.worker_alive,true);
      await page.getByTestId('load-status').getByText('生成語音',{exact:false}).waitFor();
      if(index===1) await page.getByTestId('load-status').getByText('模型已就緒（重用）',{exact:true}).waitFor();
      if(index===0) {
        await page.getByTestId('window-mode-mini').click();
        await page.locator('.mini-row .load-mini').filter({hasText:'生成語音'}).waitFor();
        await page.screenshot({path:new URL(`${engine}-mini-generating.png`,dir).pathname.replace(/^\/(\w:)/,'$1')});
        await invoke('set_shell',{shell:{...shell,mode:'compact',quick_input:false,click_through:false}});
        await page.getByTestId('load-status').locator('.load-current').waitFor();
        await invoke('set_shell',{shell:{...shell,mode:'full',quick_input:false,click_through:false}});
      }
      await page.screenshot({path:new URL(`${engine}-${index?'warm':'cold'}-generating.png`,dir).pathname.replace(/^\/(\w:)/,'$1')});
      const completed=await waitSnapshot(s=>s.queue?.find(q=>q.id===requestId)?.status==='completed'&&!s.current_request_id);
      const record=completed.queue.find(q=>q.id===requestId);
      const manifestPath=new URL(`../../artifacts/sessions/${completed.session_id}/jobs/${requestId}/${requestId}.json`,import.meta.url);
      const manifest=JSON.parse(await readFile(manifestPath,'utf8'));
      assert.equal(manifest.runtime_reused,index===1); assert.equal(manifest.status,'PASS');
      results.push({engine,index,requestId,sessionId:completed.session_id,manifest:manifestPath.pathname,load_seconds:manifest.load_seconds,inference_seconds:manifest.inference_seconds,runtime_reused:manifest.runtime_reused,record});
    }
  }
  assert.ok(progress.some(p=>p.phase==='playing'));
  assert.ok(progress.some(p=>p.phase==='model_load'));
  assert.deepEqual(errors,[]); assert.deepEqual(network,[]);
  await writeFile(new URL('report.json',dir),JSON.stringify({status:'PASS',surface:'root exe WebView2',url:page.url(),viewport:await page.evaluate(()=>({width:innerWidth,height:innerHeight})),results,progress,consoleErrors:errors,networkErrors:network,physical_mic_verified:false,audio_verified:false},null,2));
  console.log('PASS: native loading cancel, rejected parameter, two engines cold/warm generation and playback');
} catch(error) {
  await invoke('stop').catch(()=>{}); await invoke('speech_action',{action:{action:'stop_speaking'}}).catch(()=>{});
  await writeFile(new URL('report.json',dir),JSON.stringify({status:'FAILED',error:String(error),results,progress,consoleErrors:errors,networkErrors:network},null,2)); throw error;
} finally {
  await page.evaluate(original=>{for(const [name,saved] of Object.entries(original)) {const storage=name==='local'?localStorage:sessionStorage;storage.clear();for(const [key,value] of Object.entries(saved)) storage.setItem(key,value);}},original);
  await invoke('set_shell',{shell}); await page.reload(); await browser.close();
}
