//! 與 UI 共用真正的 EngineManager；不將程序 lifecycle 稱為 audio PASS。
use aethertune_desktop::engine_manager::{root, EngineManager};
use serde_json::json;
use std::{sync::Arc, thread, time::{Duration,Instant}};
fn main() {
    let engine=std::env::args().nth(1).expect("engine id");
    let args:Vec<String>=std::env::args().collect();
    let mut request=json!({"source":root().join("dataset/reference-voices/voice-male-m1.wav"),"reference":root().join("dataset/reference-voices/voice-female-f1.wav"),"input":"麥克風 (HyperX QuadCast S)","output":"CABLE Input (VB-Audio Virtual Cable)","host_api":"Windows DirectSound","parameters":{}});
    // RVC 預設 probe 用檔案，不在無人值守驗證中開實體麥克風。
    if engine=="rvc" {request["parameters"]=json!({"source_mode":"file"});}
    if let Some(index)=args.iter().position(|arg|arg=="--request") {
        request=serde_json::from_str(&std::fs::read_to_string(args.get(index+1).expect("request path")).expect("read request")).expect("request JSON");
    }
    let run_seconds=args.iter().position(|arg|arg=="--run-seconds").and_then(|index|args.get(index+1)).and_then(|s|s.parse::<u64>().ok());
    println!("{}", EngineManager::validate(&engine,request.clone()).unwrap());
    let mut manager=EngineManager::new();
    manager.start(&engine,request,Arc::new(|e|println!("{e}"))).unwrap();
    println!("{}",json!({"type":"probe_pid","pid":manager.pid()}));
    let seconds=std::env::args().nth(2).and_then(|s|s.parse().ok()).unwrap_or(20);
    let complete=std::env::args().any(|s|s=="--complete");
    let deadline=Instant::now()+Duration::from_secs(seconds);
    let mut passed=true;
    if let Some(seconds)=run_seconds {
        loop {
            let status=manager.status();
            if status["value"]=="RUNNING" {thread::sleep(Duration::from_secs(seconds));break;}
            if status["value"]=="ERROR" || Instant::now()>=deadline {passed=false;break;}
            thread::sleep(Duration::from_millis(200));
        }
        println!("{}",json!({"type":"probe_stream","started":passed,"run_seconds":seconds,"audio_verified":false}));
    } else if complete {
        loop {
            let status=manager.status();
            if status["value"]=="OFFLINE" && status["runner_pid"].is_number(){break;}
            if status["value"]=="ERROR" || Instant::now()>=deadline {passed=false;break;}
            thread::sleep(Duration::from_millis(200));
        }
        println!("{}",json!({"type":"probe_completion","completed":passed,"timeout_seconds":seconds,"audio_verified":false}));
    } else {thread::sleep(Duration::from_secs(seconds));}
    println!("{}",manager.status());
    println!("{}",manager.stop().unwrap());
    if !passed {std::process::exit(1);}
}
