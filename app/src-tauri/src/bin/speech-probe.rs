//! 無視窗驗證正式 SpeechManager；不模擬模型／音訊，也不更動預設裝置。
use aethertune_desktop::speech_manager::SpeechManager;
use serde_json::json;
use std::{fs, sync::Arc, thread, time::{Duration, Instant, SystemTime, UNIX_EPOCH}};

fn run() -> Result<(), String> {
    let args:Vec<String>=std::env::args().collect();
    if args.len()<4 {return Err("usage: speech-probe <cosyvoice|breeze> <voice-profile-id[,alternate-id]> <UTF8-text-file> [count=1] [cancel-after-seconds|playing]".into());}
    let text=fs::read_to_string(&args[3]).map_err(|e|e.to_string())?;
    let count:usize=args.get(4).map(|s|s.parse()).transpose().map_err(|e|format!("{e}"))?.unwrap_or(1);
    if !(1..=20).contains(&count) {return Err("count 須介於 1 與 20".into());}
    let cancel_on_playing=args.get(5).is_some_and(|s|s=="playing");
    let cancel_after:Option<u64>=args.get(5).filter(|_|!cancel_on_playing).map(|s|s.parse()).transpose().map_err(|e|format!("{e}"))?;
    let cancel_test=cancel_on_playing || cancel_after.is_some();
    let voices:Vec<&str>=args[2].split(',').collect();
    let lines:Vec<&str>=text.lines().filter(|s|!s.trim().is_empty()).collect();
    if lines.is_empty() {return Err("text file 不可為空".into());}
    let sink: aethertune_desktop::process_manager::Sink=Arc::new(|event| {
        if event["type"]=="log" || event["type"]=="service_exit" { println!("{event}"); }
    });
    let mut manager=SpeechManager::default();
    println!("{}",json!({"type":"initial","snapshot":manager.status(sink.clone())?}));
    for index in 0..count {
        let utterance=if count>1 {lines[index%lines.len()]}else{text.trim()};
        println!("{}",manager.action(json!({"action":"submit","enqueue":true,"request":{"source":"manual","text":utterance,"engine_id":args[1],"voice_profile_id":voices[index%voices.len()],"metadata":{"route":{"output":"CABLE Input (VB-Audio Virtual Cable)","host_api":"Windows DirectSound","rack_profile_id":"seed-vc-neutral","route_profile_id":"seed-vc-virtual-route"}}}}),sink.clone())?);
    }
    let started=Instant::now();
    let mut cancelled=false;
    let mut playing_since:Option<Instant>=None;
    let mut previous=String::new();
    let result=loop {
        let snapshot=manager.snapshot();
        let current=serde_json::to_string(&snapshot).unwrap();
        if current!=previous {println!("{}",json!({"type":"probe_snapshot","snapshot":snapshot}));previous=current;}
        if snapshot["service_alive"]!=true {break Err("service crash".to_owned());}
        if snapshot["audio_blocked"]==true {break Err("音訊 driver 無法確認回收；停止此驗證批次，請 Exit 後重新啟動".to_owned());}
        if snapshot["state"]=="PLAYING" {playing_since.get_or_insert_with(Instant::now);}else{playing_since=None;}
        // 等到播放狀態持續一秒，再由獨立 CABLE capture 確認取消前確有音訊。
        if !cancelled && (cancel_after.is_some_and(|seconds|started.elapsed()>=Duration::from_secs(seconds)) || (cancel_on_playing && playing_since.is_some_and(|at|at.elapsed()>=Duration::from_secs(1)))) {
            println!("{}",json!({"type":"probe_cancel","request_id":snapshot["current_request_id"],"at_unix_ms":SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_millis(),"mode":if cancel_on_playing{"playing"}else{"generation"}}));
            println!("{}",manager.action(json!({"action":"stop_speaking"}),sink.clone())?);cancelled=true;
        }
        let queue=snapshot["queue"].as_array().ok_or("missing queue")?;
        if queue.iter().any(|r|r["error"]["code"]=="CANCEL_CLEANUP_FAILED") {break Err("取消程序清理未驗證；停止測試，不啟動後續 request".to_owned());}
        if queue.iter().any(|r|r["status"]=="failed") {break Err("真實 TTS request 失敗；停止此驗證批次，請讀 probe_snapshot".to_owned());}
        if queue.len()>=count && queue.iter().all(|r|matches!(r["status"].as_str(),Some("completed"|"cancelled"|"failed"))) {
            if !cancel_test && queue.iter().any(|r|r["status"]!="completed") {break Err("request 未完成播放".to_owned());}
            if cancel_test && !queue.iter().any(|r|r["status"]=="cancelled") {break Err("取消測試未實際取消 request".to_owned());}
            break Ok(());
        }
        // 這台 PC 的 runner 每句重新載入模型；給每個 request 有界時間，
        // 不讓 20 次真實測試受單句固定 timeout 截斷。
        if started.elapsed()>Duration::from_secs(720*count as u64) {break Err("probe 超時".to_owned());}
        thread::sleep(Duration::from_millis(200));
    };
    manager.shutdown()?;
    println!("{}",json!({"type":"probe_result","status":if result.is_ok(){"PASS"}else{"BLOCKED"},"service_alive":manager.snapshot()["service_alive"],"cancel_test":cancel_test,"cancel_on_playing":cancel_on_playing,"request_count":count}));
    result
}
fn main() {if let Err(e)=run(){eprintln!("{e}");std::process::exit(1);}}
