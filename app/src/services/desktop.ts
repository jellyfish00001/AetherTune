import { invoke, isTauri } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import seed from '../../../contracts/engines/seed-vc.json';
import mean from '../../../contracts/engines/meanvc2.json';
import xvc from '../../../contracts/engines/xvc.json';
import rvc from '../../../contracts/engines/rvc.json';
import cosy from '../../../contracts/engines/cosyvoice.json';
import breeze from '../../../contracts/engines/breeze.json';
export type Manifest = {id:string;name:string;family?:string;referenceVoice?:boolean;capabilities:string[];classification:string;adapter:string;implementation:string;limitations:string[];parameters:unknown[]};
export type Shell = {mode:'full'|'compact'|'mini';opacity:number;always_on_top:boolean;locked:boolean;click_through:boolean;visibility_hotkey:string;voice_hotkey:string};
export type VcPostFx = {
  enabled: boolean;
  wet: number;
  low_db: number;
  mid_db: number;
  high_db: number;
  compressor_threshold_db: number;
  compressor_ratio: number;
  reverb_mix: number;
  output_gain_db: number;
};
export type RuntimeStatus = {device?: string;gpu?: string;[key:string]: unknown};
export type StatusMetrics = {
  input_peak?: number | null;
  output_peak?: number | null;
  p95_ms?: number | null;
  rtf?: number | null;
  input_drops?: number | null;
  output_drops?: number | null;
  underruns?: number | null;
  blocks?: number | null;
  [key:string]: unknown;
};
export type Status = {value:string;engine_id:string|null;reason:string;audio_verified:false;service_alive?:boolean;error?:{message:string};metrics?:StatusMetrics;runtime?:RuntimeStatus};
export const native = isTauri();
export const defaultShell:Shell = {mode:'full',opacity:.94,always_on_top:false,locked:false,click_through:false,visibility_hotkey:'Ctrl+Alt+A',voice_hotkey:'Ctrl+Alt+V'};
export const previewManifests = [seed,mean,xvc,rvc,cosy,breeze] as Manifest[];
// 預覽沒有後端或原生視窗能力；不得回傳假的 Start／Stop 成功。
export async function command<T>(name:string,args?:Record<string,unknown>):Promise<T> {
  if (!native) throw new Error('瀏覽器預覽無法控制原生視窗與 backend；請開啟 Tauri App。');
  return invoke<T>(name,args);
}
export function subscribe<T>(name:string,callback:(value:T)=>void) {
  return listen<T>(name,event=>callback(event.payload));
}
