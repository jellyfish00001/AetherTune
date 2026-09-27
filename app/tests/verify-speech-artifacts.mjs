// 驗證正式 probe 的 request／Transcript artifacts，不以 exit 0 取代已完成播放證據。
import {readFileSync,readdirSync,writeFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import Ajv from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
const file=process.argv[2];
assert.ok(file,'usage: node tests/verify-speech-artifacts.mjs <probe.jsonl>');
const events=readFileSync(file,'utf8').split(/\r?\n/).filter(Boolean).flatMap(line=>{try{return [JSON.parse(line)];}catch{return [];}});
const final=events.filter(e=>e.type==='probe_snapshot').at(-1)?.snapshot;
const result=events.findLast(e=>e.type==='probe_result');
assert.ok(final&&result,'probe 尚未完整結束');
assert.equal(result.status,'PASS');
assert.equal(result.service_alive,false);
assert.equal(final.queue.length,result.request_count);
assert.equal(new Set(final.queue.map(q=>q.id)).size,final.queue.length);
const ajv=new Ajv({allErrors:true,allowUnionTypes:true});addFormats(ajv);
for(const file of readdirSync(new URL('../../contracts/schemas/',import.meta.url)).filter(f=>f.endsWith('.json')))ajv.addSchema(JSON.parse(readFileSync(new URL('../../contracts/schemas/'+file,import.meta.url),'utf8')),file);
const transcript=ajv.getSchema('transcript-event.schema.json');
const state=ajv.getSchema('tts-state.schema.json');
for(const event of events.filter(e=>e.type==='probe_snapshot'||e.type==='initial')){
  // Native bridge 額外附上 process health；canonical snapshot 使用 Python 本體。
  const {service_alive,service_pid,error,...snapshot}=event.snapshot;
  assert.ok(state({type:'speech_snapshot',snapshot}),JSON.stringify(state.errors));
}
for(const event of final.transcript){
  assert.ok(transcript(event),JSON.stringify(transcript.errors));
  assert.equal(event.source_type,'self');
  assert.equal(event.provider,'manual_text');
  assert.equal(event.transcript_provider,'manual_text');
  assert.equal(event.speech_status,'completed');
}
const completed=final.queue.filter(q=>q.status==='completed');
const root=fileURLToPath(new URL('../../',import.meta.url));
const sha256=path=>createHash('sha256').update(readFileSync(path)).digest('hex');
// 對照實際 runner manifest、reference 與輸出檔；Voice 切換不能只驗證 UI label。
for(const item of completed){
  const evidence=JSON.parse(readFileSync(resolve(root,'artifacts/sessions',final.session_id,item.id+'.evidence.json'),'utf8'));
  assert.equal(evidence.runner_manifest.status,'PRESENT');
  const runner=evidence.runner_manifest.manifest;
  assert.equal(runner.status,'PASS');
  assert.equal(runner.text.trim(),item.text.trim());
  const reference=item.profile_snapshot.references[item.engine_id];
  const prompt=runner.prompt_audio??runner.reference_audio;
  assert.ok(prompt?.sha256,'runner 必須保存 reference hash');
  assert.equal(prompt.sha256,sha256(resolve(root,reference.audio_path)));
  assert.equal(evidence.output.sha256,sha256(evidence.output.path));
  assert.equal(runner.output.sha256,evidence.output.sha256);
  assert.ok(runner.output_validation.peak>0);
  assert.match(evidence.model_fingerprint.aggregate_sha256,/^[0-9a-f]{64}$/);
  assert.ok(evidence.model_fingerprint.files.length>0);
  assert.ok(evidence.model_fingerprint.files.every(f=>f.exists&&f.hash_mode==='full'&&/^[0-9a-f]{64}$/.test(f.sha256)));
  assert.equal(evidence.route_resolution.resolved_output,'CABLE Input (VB-Audio Virtual Cable)');
  assert.equal(evidence.route_resolution.resolved_host_api,'Windows DirectSound');
  assert.equal(evidence.route_resolution.rendered_sample_rate,48000);
  assert.equal(evidence.route_resolution.rendered_channels,2);
}
assert.equal(final.transcript.length,completed.length);
if(result.cancel_test){
  assert.ok(final.queue.some(q=>q.status==='cancelled'));
  for(const item of final.queue.filter(q=>q.status==='cancelled')){
    assert.equal(item.error?.code,'CANCELLED','unverified cancellation cleanup 不能判 PASS');
    assert.notEqual(item.error?.cleanup_verified,false);
  }
}
else{assert.equal(completed.length,result.request_count);}
const submitted=events.filter(e=>e.type==='speech_ack'&&e.accepted&&e.result?.request_id).map(e=>e.result.request_id);
assert.equal(submitted.length,result.request_count);
{
  const completedOrder=submitted.filter(id=>completed.some(q=>q.id===id));
  assert.deepEqual(final.transcript.map(t=>t.request_id),completedOrder,'FIFO completed order 必須與 ACK submission order 一致');
  const byId=new Map(completed.map(q=>[q.id,q]));
  for(let i=1;i<completedOrder.length;i++)assert.ok(Date.parse(byId.get(completedOrder[i]).metrics.generation_started_at)>=Date.parse(byId.get(completedOrder[i-1]).metrics.playback_completed_at),'下一句 generation 只能在上一句 playback completed 後開始');
}
for(const item of completed){
  const metrics=item.metrics;
  for(const field of ['request_created_at','generation_started_at','first_audio_at','playback_started_at','playback_completed_at'])assert.ok(metrics[field],`missing ${field}`);
  assert.ok(Date.parse(metrics.playback_completed_at)>=Date.parse(metrics.playback_started_at));
  assert.ok(Date.parse(metrics.first_audio_at)>=Date.parse(metrics.generation_started_at));
  assert.ok(Date.parse(metrics.playback_started_at)>=Date.parse(metrics.first_audio_at));
  assert.ok(metrics.total_response_ms>=metrics.generation_latency_ms);
}
const sessionDir=new URL('../../artifacts/sessions/'+final.session_id+'/',import.meta.url);
const session=JSON.parse(readFileSync(new URL('session.json',sessionDir),'utf8'));
const validSession=ajv.getSchema('session.schema.json');
assert.ok(validSession(session),JSON.stringify(validSession.errors));
assert.ok(session.ended_at,'Exit 必須寫入 session end');
const requests=readFileSync(new URL('requests.jsonl',sessionDir),'utf8').trim().split(/\r?\n/).filter(Boolean).map(JSON.parse);
assert.equal(requests.length,result.request_count);
for(const item of requests)assert.ok(ajv.getSchema('speech-request.schema.json')(item),JSON.stringify(ajv.getSchema('speech-request.schema.json').errors));
const exported=readFileSync(new URL('transcript.jsonl',sessionDir),'utf8').trim().split(/\r?\n/).filter(Boolean).map(JSON.parse);
assert.deepEqual(exported,final.transcript,'SQLite snapshot 與 session export 必須一致');
const report={status:'PASS',scope:'formal probe artifacts, reference/output hashes, FIFO, completed Transcript schema',requests:final.queue.length,completed:completed.length,cancelled:final.queue.filter(q=>q.status==='cancelled').length,session_id:final.session_id,
  completed_voices:[...new Set(completed.map(q=>q.voice_profile_id))],
  completed_requests:completed.map(q=>({id:q.id,text:q.text,voice:q.voice_profile_id,metrics:q.metrics}))};
writeFileSync(resolve(dirname(file),'artifact-verification.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify({...report,completed_requests:undefined},null,2));
