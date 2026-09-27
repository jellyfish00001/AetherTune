import {chromium} from 'playwright';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.connectOverCDP(process.env.AETHERTUNE_CDP??'http://127.0.0.1:9223');
const page=browser.contexts()[0].pages().find(p=>/tauri.localhost|127.0.0.1:1420/.test(p.url()));
const before=0;
await page.evaluate(async()=>{
 await window.__TAURI_INTERNALS__.invoke('stop');
 await window.__TAURI_INTERNALS__.invoke('start',{engine:'meanvc2',request:{source:'D:/AetherTune/dataset/reference-voices/voice-male-m1.wav',reference:'D:/AetherTune/dataset/reference-voices/voice-female-f1.wav',parameters:{}}});
});
const deadline=Date.now()+15000;let started=false;
while(Date.now()<deadline){started=await page.evaluate(async before=>(await window.__TAURI_INTERNALS__.invoke('logs')).slice(before).some(e=>e.type==='process_started'),before);if(started)break;await new Promise(r=>setTimeout(r,100));}
if(!started)throw new Error('本次 runner 未啟動');
await writeFile(new URL('../../artifacts/desktop/integration/exit-before.json',import.meta.url),JSON.stringify(await page.evaluate(async()=>({status:await window.__TAURI_INTERNALS__.invoke('status'),logs:await window.__TAURI_INTERNALS__.invoke('logs')})),null,2));
await browser.close();
