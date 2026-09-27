// 驗證跨 schema 參照及未來契約；這些測試不執行 Agent 或音訊。
import {readFileSync,readdirSync} from 'node:fs';
import assert from 'node:assert/strict';
import Ajv from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
const ajv=new Ajv({allErrors:true,allowUnionTypes:true});addFormats(ajv);
const read=(path)=>JSON.parse(readFileSync(new URL(path,import.meta.url),'utf8'));
for(const file of readdirSync(new URL('../../contracts/schemas/',import.meta.url)).filter(f=>f.endsWith('.json')))ajv.addSchema(read('../../contracts/schemas/'+file),file);
const profile=ajv.getSchema('voice-profile.schema.json');
const profiles=readdirSync(new URL('../../contracts/voices/',import.meta.url)).filter(f=>f.endsWith('.json')).map(f=>read('../../contracts/voices/'+f));
for(const value of profiles)assert.ok(profile(value),JSON.stringify(profile.errors));
assert.equal(new Set(profiles.map(v=>v.id)).size,profiles.length);
const request=ajv.getSchema('speech-request.schema.json');
const event={id:'8f455539-de77-4c42-b448-0e073b606e5c',session_id:'49de5035-1523-4494-a4c6-cb3cde596595',source:'manual',text:'契約測試',engine_id:'cosyvoice',voice_profile_id:profiles[0].id,priority:100,interrupt_policy:'queue',metadata:{},created_at:'2026-09-27T12:31:01Z',status:'queued',metrics:{},error:null};
assert.ok(request(event),JSON.stringify(request.errors));
assert.ok(request({...event,source:'agent'}),'future Agent source 必須留在契約；service 仍拒絕提交');
assert.ok(request({...event,status:'ready'}));
assert.equal(request({...event,engine_id:'cosyvoice3'}),false);
assert.equal(request({...event,interrupt_policy:'auto'}),false);
const agent=ajv.getSchema('agent-reply.schema.json');
assert.ok(agent({text:'未來回覆',emotion:null,actions:[],metadata:{}}),JSON.stringify(agent.errors));
assert.equal(agent({type:'speech_ack',command_id:'ack',accepted:true}),false,'AgentReply 不能與 service ACK 混淆');
const state=ajv.getSchema('tts-state.schema.json');
for(const value of ['IDLE','QUEUED','GENERATING','BUFFERING','PLAYING','STOPPING','ERROR']){
  assert.ok(state({type:'speech_snapshot',snapshot:{session_id:event.session_id,state:value,queue:[event],transcript:[],profiles,settings:{interrupt_policy:'queue',enter_to_send:true},recent_phrases:[],favorites:[],mic_enabled:false,capabilities:{microphone:'WAITING',manual_text:'implemented',agent_reply:'PLANNED'}}}),JSON.stringify(state.errors));
}
console.log('PASS: Manual SpeechRequest / VoiceProfile / AgentReply / TTS state contracts and negatives');
