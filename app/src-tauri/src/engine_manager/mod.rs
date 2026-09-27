use std::{collections::VecDeque, fs::{self, File}, io::Write, path::PathBuf, process::Command, sync::{Arc, Mutex}, time::{SystemTime, UNIX_EPOCH}};
use serde_json::{json, Value};
use crate::process_manager::{Process, Sink};

pub fn root() -> PathBuf {
    std::env::var_os("AETHERTUNE_ROOT").map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().unwrap().parent().unwrap().to_owned())
}
pub fn discover() -> Result<Vec<Value>, String> {
    ["seed-vc", "meanvc2", "xvc", "rvc", "cosyvoice", "breeze"].iter().map(|id| {
        let data = fs::read_to_string(root().join(format!("contracts/engines/{id}.json"))).map_err(|e| e.to_string())?;
        serde_json::from_str(&data).map_err(|e| e.to_string())
    }).collect()
}
#[derive(Default)]
pub struct EngineManager { process: Option<Process>, snapshot: Arc<Mutex<Value>>, logs: Arc<Mutex<VecDeque<Value>>>, stopping: Arc<Mutex<bool>> }
impl EngineManager {
    pub fn new() -> Self { Self { snapshot: Arc::new(Mutex::new(json!({"value":"OFFLINE","audio_verified":false,"reason":"尚未啟動","engine_id":null}))), ..Self::default() } }
    pub fn status(&self) -> Value { let mut s = self.snapshot.lock().unwrap().clone(); s["service_alive"] = json!(self.process.as_ref().is_some_and(|p| p.alive())); s }
    pub fn logs(&self) -> Vec<Value> { self.logs.lock().unwrap().iter().cloned().collect() }
    fn command(engine: &str, request: Value) -> Result<Command, String> {
        if !["seed-vc", "meanvc2", "xvc"].contains(&engine) { return Err("BACKEND_UNAVAILABLE: 此 engine 僅有契約".into()); }
        let folder = root().join("artifacts/desktop/control"); fs::create_dir_all(&folder).map_err(|e| e.to_string())?;
        let nonce = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let path = folder.join(format!("request-{nonce}.json"));
        fs::write(&path, serde_json::to_vec(&request).unwrap()).map_err(|e| e.to_string())?;
        let python = root().join(format!("tools/venvs/{engine}/Scripts/python.exe"));
        if !python.is_file() { return Err(format!("MODEL_NOT_FOUND: {}", python.display())); }
        let mut command = Command::new(python);
        command.args(["-u", "-B"]).arg(root().join("services/engines/runner_service.py"))
            .arg("--root").arg(root()).arg("--engine").arg(engine).arg("--request").arg(path).current_dir(root());
        Ok(command)
    }
    pub fn validate(engine: &str, request: Value) -> Result<Value, String> {
        let mut command = Self::command(engine, request)?; command.arg("--validate");
        #[cfg(windows)] { use std::os::windows::process::CommandExt; command.creation_flags(0x08000000); }
        let output = command.output().map_err(|e| e.to_string())?;
        Ok(json!({"valid":output.status.success(),"events":String::from_utf8_lossy(&output.stdout).lines().filter_map(|s| serde_json::from_str::<Value>(s).ok()).collect::<Vec<_>>(),"stderr":String::from_utf8_lossy(&output.stderr)}))
    }
    pub fn start(&mut self, engine: &str, request: Value, external: Sink) -> Result<Value, String> {
        self.stop()?;
        self.logs.lock().unwrap().clear();
        *self.stopping.lock().unwrap() = false;
        *self.snapshot.lock().unwrap() = json!({"value":"VALIDATING","engine_id":engine,"audio_verified":false,"reason":"啟動 orchestration service"});
        let snapshot = self.snapshot.clone(); let logs = self.logs.clone(); let stopping = self.stopping.clone();
        let log_dir = root().join("artifacts/desktop/logs"); fs::create_dir_all(&log_dir).map_err(|e| e.to_string())?;
        let nonce = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let file = Arc::new(Mutex::new(File::create(log_dir.join(format!("{engine}-{nonce}.jsonl"))).map_err(|e|e.to_string())?));
        let sink: Sink = Arc::new(move |event| {
            { let mut f = file.lock().unwrap(); let _ = writeln!(f,"{event}"); let _ = f.flush(); }
            { let mut l = logs.lock().unwrap(); l.push_back(event.clone()); if l.len()>500 { l.pop_front(); } }
            match event["type"].as_str() {
                Some("state") if !*stopping.lock().unwrap() => {
                    let mut s=snapshot.lock().unwrap();
                    for (key,value) in event.as_object().unwrap() { s[key]=value.clone(); }
                }
                Some("process_started") => { let mut s=snapshot.lock().unwrap(); s["runner_pid"]=event["pid"].clone(); s["adapter"]=event["adapter"].clone(); }
                Some("artifact") => { snapshot.lock().unwrap()["artifact"]=event["path"].clone(); }
                Some("error") => { let mut s = snapshot.lock().unwrap(); s["error"] = event.clone(); }
                Some("service_exit") if !*stopping.lock().unwrap() => {
                    let mut s = snapshot.lock().unwrap(); if s["value"] != "ERROR" { s["value"] = json!("ERROR"); s["reason"] = json!("service 非預期結束；可重新啟動"); }
                }
                _ => {}
            }
            external(event);
        });
        let result = Self::command(engine, request).and_then(|cmd| Process::spawn(cmd, sink));
        match result {
            Ok(mut process) => { if let Err(e) = process.send(json!({"command":"start"})) { let _=process.stop(); return Err(e); } self.process = Some(process); }
            Err(e) => { self.snapshot.lock().unwrap()["value"] = json!("ERROR"); self.snapshot.lock().unwrap()["reason"] = json!(e); return Err(e); }
        }
        Ok(self.status())
    }
    pub fn stop(&mut self) -> Result<Value, String> {
        *self.stopping.lock().unwrap() = true;
        if let Some(mut process) = self.process.take() { self.snapshot.lock().unwrap()["value"] = json!("STOPPING"); process.stop()?; }
        let mut s = self.snapshot.lock().unwrap(); s["value"] = json!("OFFLINE"); s["reason"] = json!("受管制的程序樹已釋放"); s["audio_verified"] = json!(false); drop(s);
        Ok(self.status())
    }
    pub fn pid(&self) -> Option<u32> { self.process.as_ref().map(|p| p.id()) }
}
