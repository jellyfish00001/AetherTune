//! 與 UI 共用真正的 EngineManager；不將程序 lifecycle 稱為 audio PASS。
use aethertune_desktop::engine_manager::{root, EngineManager};
use serde_json::json;
use std::{sync::Arc, thread, time::Duration};
fn main() {
    let engine=std::env::args().nth(1).expect("engine id");
    let request=json!({"source":root().join("dataset/reference-voices/voice-male-m1.wav"),"reference":root().join("dataset/reference-voices/voice-female-f1.wav"),"input":"麥克風 (HyperX QuadCast S)","output":"CABLE Input (VB-Audio Virtual Cable)","host_api":"Windows DirectSound","parameters":{}});
    println!("{}", EngineManager::validate(&engine,request.clone()).unwrap());
    let mut manager=EngineManager::new();
    manager.start(&engine,request,Arc::new(|e|println!("{e}"))).unwrap();
    println!("{}",json!({"type":"probe_pid","pid":manager.pid()}));
    let seconds=std::env::args().nth(2).and_then(|s|s.parse().ok()).unwrap_or(20);
    thread::sleep(Duration::from_secs(seconds));
    println!("{}",manager.status());
    println!("{}",manager.stop().unwrap());
}
