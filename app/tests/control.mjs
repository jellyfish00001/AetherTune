// 只供本機驗證使用；不攜帶任意 script 或 shell command 到 UI。
import {chromium} from 'playwright';
const browser=await chromium.connectOverCDP(process.env.AETHERTUNE_CDP??'http://127.0.0.1:9223');
const page=browser.contexts()[0].pages().find(p=>/tauri.localhost|127.0.0.1:1420/.test(p.url()));
const action=process.argv[2];
if(action==='exit')await page.evaluate(()=>window.__TAURI_INTERNALS__.invoke('exit')).catch(()=>{});
else if(action==='shell')console.log(JSON.stringify(await page.evaluate(()=>window.__TAURI_INTERNALS__.invoke('window_status'))));
else if(action==='restore')await page.evaluate(async()=>{const s=await window.__TAURI_INTERNALS__.invoke('shell_status');await window.__TAURI_INTERNALS__.invoke('set_shell',{shell:{...s,mode:'full',click_through:false}});});
else throw new Error('action 必須是 exit / shell / restore');
await browser.close();
