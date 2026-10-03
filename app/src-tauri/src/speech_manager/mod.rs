//! 文字控制通道；音訊僅留在 Python，沿用 Windows Job 的程序所有權。
use std::{collections::HashMap, process::Command, sync::{Arc, Condvar, Mutex}, time::{Duration, Instant, SystemTime, UNIX_EPOCH}};
use serde_json::{json, Value};
use crate::{engine_manager::root, process_manager::{Process, Sink}};

fn update_progress(snapshot: &mut Value, progress: &Value) {
    if progress["request_id"].is_string() && progress["request_id"] == snapshot["current_request_id"] {
        snapshot["progress"] = progress.clone();
    }
}

struct Shared {
    snapshot: Value,
    acknowledgements: HashMap<String, Value>,
    exited: bool,
}
pub struct SpeechManager {
    process: Option<Process>,
    shared: Arc<(Mutex<Shared>, Condvar)>,
}
impl Default for SpeechManager {
    fn default() -> Self {
        Self { process: None, shared: Arc::new((Mutex::new(Shared {
            snapshot: json!({"state":"IDLE","session_id":null,"queue":[],"transcript":[],"profiles":[],"settings":{"interrupt_policy":"queue","enter_to_send":true},"recent_phrases":[],"favorites":[],"mic_enabled":false,"capabilities":{"microphone":"WAITING","manual_text":"implemented","agent_reply":"PLANNED"}}),
            acknowledgements: HashMap::new(), exited: false,
        }), Condvar::new())) }
    }
}
impl SpeechManager {
    fn ensure(&mut self, external: Sink) -> Result<(), String> {
        if self.process.as_ref().is_some_and(|p|p.alive()) { return Ok(()); }
        self.shutdown()?;
        let python = root().join("tools/venvs/seed-vc/Scripts/python.exe");
        if !python.is_file() { return Err("TTS_SERVICE_UNAVAILABLE: 缺少既有 Windows Python runtime".into()); }
        let mut command = Command::new(python);
        command.args(["-u", "-B", "-m", "services.tts.service"]).arg("--root").arg(root()).env("PYTHONIOENCODING","utf-8").current_dir(root());
        let result=self.spawn(command, external);
        if result.is_err() { let _=self.shutdown(); }
        result
    }
    fn spawn(&mut self, command: Command, external: Sink) -> Result<(), String> {
        { let mut s=self.shared.0.lock().unwrap(); s.exited=false; s.acknowledgements.clear(); s.snapshot["session_id"]=Value::Null; }
        let shared=self.shared.clone();
        self.process=Some(Process::spawn(command, Arc::new(move |event| {
            {
                let (lock, notify)=&*shared;
                let mut s=lock.lock().unwrap();
                match event["type"].as_str() {
                    Some("speech_snapshot") => s.snapshot=event["snapshot"].clone(),
                    Some("speech_progress") => {
                        // 精簡心跳只更新目前句子，不讓舊 worker 事件污染下一句。
                        update_progress(&mut s.snapshot, &event["progress"]);
                    },
                    Some("speech_ack") => if let Some(id)=event["command_id"].as_str() {
                        // 超時回應有界保留，避免異常 service 無限增長記憶體。
                        if s.acknowledgements.len()>=128 { s.acknowledgements.clear(); }
                        s.acknowledgements.insert(id.to_owned(), event.clone());
                    },
                    Some("service_exit") => { s.exited=true; s.snapshot["state"]=json!("ERROR"); s.snapshot["error"]=json!("TTS service 已結束；重新提交可建立新 session"); },
                    _ => {},
                }
                notify.notify_all();
            }
            external(event);
        }))?);
        let deadline=Instant::now()+Duration::from_secs(30);
        let (lock, notify)=&*self.shared;
        let mut s=lock.lock().unwrap();
        while s.snapshot["session_id"].is_null() && !s.exited {
            let remaining=deadline.saturating_duration_since(Instant::now());
            if remaining.is_zero() { return Err("TTS_SERVICE_TIMEOUT: 未收到初始狀態".into()); }
            s=notify.wait_timeout(s,remaining).unwrap().0;
        }
        if s.exited { return Err("TTS_SERVICE_UNAVAILABLE: 初始化失敗".into()); }
        Ok(())
    }
    pub fn status(&mut self, external: Sink) -> Result<Value, String> {
        self.ensure(external)?;
        Ok(self.snapshot())
    }
    pub fn snapshot(&self) -> Value {
        let mut s=self.shared.0.lock().unwrap().snapshot.clone();
        s["service_alive"]=json!(self.process.as_ref().is_some_and(|p|p.alive()));
        s["service_pid"]=json!(self.process.as_ref().map(|p|p.id()));
        s
    }
    pub fn action(&mut self, mut action: Value, external: Sink) -> Result<Value, String> {
        let name=action["action"].as_str().ok_or("缺少 speech action")?;
        if !["audio_devices","submit","stop_speaking","clear_queue","remove","move_up","move_down","speak_now","settings","favorite","status"].contains(&name) {
            return Err("不支援的 speech action".into());
        }
        self.ensure(external)?;
        let id=SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos().to_string();
        action["command_id"]=json!(id);
        self.process.as_mut().unwrap().send(action)?;
        let deadline=Instant::now()+Duration::from_secs(5);
        let (lock,notify)=&*self.shared;
        let mut s=lock.lock().unwrap();
        loop {
            if let Some(ack)=s.acknowledgements.remove(&id) {
                return if ack["accepted"]==true { Ok(ack) } else {
                    let error=ack["error"].as_str().map(str::to_owned).unwrap_or_else(|| {
                        format!("{}: {}",ack["error"]["code"].as_str().unwrap_or("TTS_REQUEST_REJECTED"),ack["error"]["message"].as_str().unwrap_or("TTS request 被拒絕"))
                    });Err(error)
                };
            }
            if s.exited { return Err("TTS service 已結束".into()); }
            let remaining=deadline.saturating_duration_since(Instant::now());
            if remaining.is_zero() { return Err("TTS_CONTROL_TIMEOUT: 未收到回應；請檢查 Queue，避免重複提交".into()); }
            s=notify.wait_timeout(s,remaining).unwrap().0;
        }
    }
    pub fn shutdown(&mut self) -> Result<(), String> {
        if let Some(mut process)=self.process.take() {
            let _=process.send(json!({"action":"shutdown"}));
            // WSL group identity／TERM-KILL 回收在 Windows Job 關閉前完成。
            process.stop_with_grace(Duration::from_secs(12))?;
        }
        Ok(())
    }
}
impl Drop for SpeechManager { fn drop(&mut self) { let _=self.shutdown(); } }

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn progress_does_not_cross_request_identity() {
        let mut snapshot=json!({"current_request_id":"current"});
        update_progress(&mut snapshot, &json!({"request_id":"previous","phase":"generating"}));
        assert!(snapshot.get("progress").is_none());
        update_progress(&mut snapshot, &json!({"request_id":"current","phase":"model_load"}));
        assert_eq!(snapshot["progress"]["phase"],"model_load");
        snapshot["current_request_id"]=Value::Null;
        update_progress(&mut snapshot, &json!({"request_id":"current","phase":"generating"}));
        assert_eq!(snapshot["progress"]["phase"],"model_load");
    }
    #[test]
    fn json_control_ack_and_cleanup() {
        let python=root().join("tools/venvs/seed-vc/Scripts/python.exe");
        let mut command=Command::new(python);
        command.args(["-u","-c", "import json,sys; print(json.dumps({'type':'speech_snapshot','snapshot':{'session_id':'fixture','state':'IDLE'}}),flush=True)\nfor line in sys.stdin:\n c=json.loads(line)\n if c.get('action')=='shutdown': break\n print(json.dumps({'type':'speech_ack','command_id':c.get('command_id'),'accepted':c.get('action')!='favorite','error':{'code':'QUEUE_BUSY','message':'fixture reject'}}),flush=True)"]);
        let mut m=SpeechManager::default();
        m.spawn(command, Arc::new(|_|{})).unwrap();
        assert_eq!(m.snapshot()["state"],"IDLE");
        assert_eq!(m.action(json!({"action":"status"}), Arc::new(|_|{})).unwrap()["accepted"],true);
        assert_eq!(m.action(json!({"action":"favorite","text":"fixture"}),Arc::new(|_|{})).unwrap_err(),"QUEUE_BUSY: fixture reject");
        assert!(m.action(json!({"action":"arbitrary_executable"}),Arc::new(|_|{})).is_err());
        m.shutdown().unwrap();
        assert_eq!(m.snapshot()["service_alive"],false);
    }
}
