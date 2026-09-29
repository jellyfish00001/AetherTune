// 只供本機驗證使用；不攜帶任意 script 或 shell command 到 UI。
import {chromium} from 'playwright';
const browser=await chromium.connectOverCDP(process.env.AETHERTUNE_CDP??'http://127.0.0.1:9223');
const page=browser.contexts()[0].pages().find(p=>/tauri.localhost|127.0.0.1:1420/.test(p.url()));
const action=process.argv[2];
if(action==='exit')await page.evaluate(()=>window.__TAURI_INTERNALS__.invoke('exit')).catch(()=>{});
else if(action==='shell')console.log(JSON.stringify(await page.evaluate(()=>window.__TAURI_INTERNALS__.invoke('window_status'))));
else if(action==='restore')await page.evaluate(async()=>{const s=await window.__TAURI_INTERNALS__.invoke('shell_status');await window.__TAURI_INTERNALS__.invoke('set_shell',{shell:{...s,mode:'full',click_through:false}});});
else if(action==='devices'){
  // 只切換設定畫面並讀取下拉選單；不啟動 VC runner 或改動 Windows 預設裝置。
  await page.getByLabel('Mode',{exact:true}).selectOption('streaming_vc');
  await page.getByLabel('Input device').waitFor();
  const inputs=await page.getByLabel('Input device').locator('option').allTextContents();
  const outputs=await page.getByLabel('Output device').locator('option').allTextContents();
  const hostApis=await page.getByLabel('Host API').locator('option').allTextContents();
  await page.screenshot({path:new URL('../../output/playwright/native-vc-device-dropdowns.png',import.meta.url).pathname.replace(/^\/(\w:)/,'$1')});
  await page.getByLabel('Mode',{exact:true}).selectOption('text_to_speech');
  console.log(JSON.stringify({inputOptions:inputs.length,outputOptions:outputs.length,hostApis:hostApis.length,selectedOutput:await page.getByLabel('TTS Output').locator('option:checked').textContent()}));
}
else throw new Error('action 必須是 exit / shell / restore / devices');
await browser.close();
