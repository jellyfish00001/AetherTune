import {readFileSync,readdirSync} from 'node:fs';
import assert from 'node:assert/strict';
import Ajv from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
const ajv=new Ajv({allErrors:true,allowUnionTypes:true});addFormats(ajv);
const read=p=>JSON.parse(readFileSync(new URL(p,import.meta.url),'utf8'));
ajv.addSchema(read('../../contracts/schemas/runtime-progress.schema.json'), 'runtime-progress.schema.json');
const manifestValidator=ajv.compile(read('../../contracts/schemas/engine-manifest.schema.json'));
const engines=readdirSync(new URL('../../contracts/engines/',import.meta.url)).map(p=>read('../../contracts/engines/'+p));
assert.equal(engines.length,6);
for(const e of engines){assert.ok(manifestValidator(e),JSON.stringify(manifestValidator.errors));assert.equal(new Set(e.parameters.map(p=>p.name)).size,e.parameters.length);}
const state=ajv.compile(read('../../contracts/schemas/backend-state.schema.json'));
const progress=ajv.getSchema('runtime-progress.schema.json');
const loading={phase:'model_load',elapsed_seconds:3,last_progress_seconds_ago:1,observed_at:'2026-10-03T00:00:00Z',worker_alive:true};
assert.ok(progress(loading));
for(const invalid of [{...loading,phase:'percent_90'},{...loading,worker_alive:'yes'},{...loading,elapsed_seconds:-1},{...loading,observed_at:'bad date'}]) assert.equal(progress(invalid),false);
const estimates=read('../../contracts/model-load-estimates.json');
for(const e of estimates.estimates) {
  const manifest=engines.find(m=>m.id===e.engine); assert.ok(manifest);
  assert.ok(e.seconds.length===2&&e.seconds.every(v=>Number.isFinite(v)&&v>=0)&&e.seconds[0]<=e.seconds[1]);
  assert.ok(Number.isInteger(e.samples)&&e.samples>0&&e.sources.length>0);
  if(e.model) assert.ok(manifest.parameters.find(p=>p.name===(e.engine==='rvc'?'model_id':'model')).options.includes(e.model));
  if(e.method) assert.ok(manifest.parameters.find(p=>p.name==='f0_method').options.includes(e.method));
}
assert.ok(state({type:'state',engine_id:'seed-vc',value:'LOADING',reason:'TEMPORARY',audio_verified:false}));
assert.equal(state({type:'state',engine_id:'seed-vc',value:'PROCESS_STARTED',reason:'fake',audio_verified:false}),false);
assert.equal(state({type:'state',engine_id:'seed-vc',value:'RUNNING',reason:'fake audio',audio_verified:true}),false);
const transcript=ajv.compile(read('../../contracts/schemas/transcript-event.schema.json'));
const event={id:'8f455539-de77-4c42-b448-0e073b606e5c',session_id:'49de5035-1523-4494-a4c6-cb3cde596595',source_id:'mic-main',source_type:'self',speaker_id:null,device_id:'endpoint-id',started_at:'2026-09-27T12:31:01Z',ended_at:'2026-09-27T12:31:03Z',language:'zh',text:'契約測試',confidence:.94,provider:'faster-whisper',transcript_provider:'parallel_stt'};
assert.ok(transcript(event));assert.equal(transcript({...event,confidence:2}),false);assert.equal(transcript({...event,source_type:'Alice'}),false);
const session=ajv.compile(read('../../contracts/schemas/session.schema.json'));
assert.ok(session({id:event.session_id,started_at:event.started_at,ended_at:null,mode:'streaming_vc',engine_id:'seed-vc',model:null,voice_profile_id:null,reference:null,parameters:{},input_device_id:null,output_device_id:null,postfx_preset:null,stt_settings:{},transcript_storage:'sqlite',export_directory:'artifacts/sessions/test'}));
console.log('PASS: 6 manifests, state vocabulary/audio boundary, transcript/session schema, negative fixtures');
