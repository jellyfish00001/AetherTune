#![cfg_attr(windows, windows_subsystem = "windows")]
use aethertune_desktop::engine_manager::{self, EngineManager};
use aethertune_desktop::speech_manager::SpeechManager;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{fs, io::Write, sync::{Arc, Mutex}, time::{Duration,SystemTime,UNIX_EPOCH}};
use tauri::{Emitter, Manager, menu::{Menu, MenuItem}, tray::{TrayIconBuilder, TrayIconEvent, MouseButton, MouseButtonState}, LogicalSize};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

#[derive(Clone, Serialize, Deserialize)]
#[serde(default)]
struct Shell {
    mode:String, opacity:f64, always_on_top:bool, locked:bool, click_through:bool,
    visibility_hotkey:String, voice_hotkey:String,
    quick_input:bool,
}
impl Default for Shell { fn default()->Self { Self { mode:"full".into(),opacity:0.94,always_on_top:false,locked:false,click_through:false,visibility_hotkey:"Ctrl+Alt+A".into(),voice_hotkey:"Ctrl+Alt+V".into(),quick_input:false } } }
struct Desktop { engine:Mutex<EngineManager>, speech:Mutex<SpeechManager>, audio_control:Mutex<()>, shell:Mutex<Shell>, last:Mutex<Option<(String,Value)>> }

fn record_action(action:&str) {
    let folder=engine_manager::root().join("artifacts/desktop");
    let _=fs::create_dir_all(&folder);
    if let Ok(mut file)=fs::OpenOptions::new().create(true).append(true).open(folder.join("window-events.jsonl")) {
        let event=json!({"unix_ms":SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_millis(),"pid":std::process::id(),"action":action});
        let _=writeln!(file,"{event}");let _=file.flush();
    }
}

// 原生診斷只輸出狀態；測試可讀取真實 flags／程序結果，無需開 remote debugging port。
fn start_diagnostics(app:tauri::AppHandle) {
    std::thread::spawn(move||loop {
        if app.get_webview_window("main").is_none(){break;}
        let d=app.state::<Desktop>();
        // 視窗查詢可能切回 UI 執行緒；先複製狀態並釋放鎖，避免 UI command 等鎖時互相卡住。
        let engine=d.engine.try_lock().ok().map(|guard|guard.status());
        let shell=d.shell.try_lock().ok().map(|guard|guard.clone());
        if let (Some(engine),Some(shell))=(engine,shell) {
            if let Ok(window)=window_status(app.clone()) {
                let snapshot=json!({"unix_ms":SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_millis(),"pid":std::process::id(),"engine":engine,"shell":shell,"window":window});
                let folder=engine_manager::root().join("artifacts/desktop");let _=fs::create_dir_all(&folder);
                let temp=folder.join("native-state.tmp");
                if fs::write(&temp,serde_json::to_vec(&snapshot).unwrap()).is_ok(){let _=fs::rename(temp,folder.join("native-state.json"));}
            }
        }
        std::thread::sleep(Duration::from_millis(250));
    });
}

fn apply_shell(app:&tauri::AppHandle, shell:&Shell)->Result<(),String> {
    let (w,h)=match shell.mode.as_str() { "full"=>(1040.,740.), "compact"=>(420.,490.), "mini"=>(420.,if shell.quick_input {260.}else{74.}), _=>return Err("未知視窗模式".into()) };
    if !(0.45..=1.).contains(&shell.opacity) { return Err("透明度須介於 0.45 與 1".into()); }
    if shell.click_through && shell.mode=="full" { return Err("Click-through 僅供 Overlay 使用".into()); }
    let window=app.get_webview_window("main").ok_or("主視窗不存在")?;
    window.set_size(LogicalSize::new(w,h)).map_err(|e|e.to_string())?;
    window.set_always_on_top(shell.always_on_top || shell.mode!="full").map_err(|e|e.to_string())?;
    window.set_resizable(shell.mode=="full").map_err(|e|e.to_string())?;
    window.set_ignore_cursor_events(shell.click_through).map_err(|e|e.to_string())?;
    app.emit("shell",shell).map_err(|e|e.to_string())?;
    Ok(())
}
fn reveal(app:&tauri::AppHandle, mode:Option<&str>) {
    let desktop=app.state::<Desktop>(); let mut shell=desktop.shell.lock().unwrap();
    if let Some(mode)=mode { shell.mode=mode.into(); }
    shell.click_through=false;
    let _=apply_shell(app,&shell);
    if let Some(w)=app.get_webview_window("main") { let _=w.unminimize(); let _=w.show(); let _=w.set_focus(); }
}
fn toggle_voice(app:&tauri::AppHandle) {
    let d=app.state::<Desktop>();
    let _control=d.audio_control.lock().unwrap();
    let mut engine=d.engine.lock().unwrap();
    if engine.status()["service_alive"]!=true && speech_blocks_vc(&d.speech.lock().unwrap().snapshot()) {
        let _=app.emit("engine-action",json!({"error":"請先完成或停止 TTS Queue，再啟動 VC runner"}));return;
    }
    let result=if engine.status()["service_alive"]==true {engine.stop()} else if let Some((id,request))=d.last.lock().unwrap().clone() {let handle=app.clone();engine.start(&id,request,Arc::new(move|e|{let _=handle.emit("engine-event",e);}))} else {Err("請先在 LIVE 選擇 Engine 與檔案，再 Start".into())};
    let _=app.emit("engine-action",json!({"result":result.as_ref().ok(),"error":result.err()}));
}
fn speech_blocks_vc(snapshot:&Value)->bool {
    // 取消未能驗證 WSL group 回收時，也不能啟動另一個 GPU／Output runner。
    ["QUEUED","GENERATING","BUFFERING","PLAYING","STOPPING"].contains(&snapshot["state"].as_str().unwrap_or("IDLE"))
        || snapshot["audio_blocked"]==true
        || snapshot["queue"].as_array().is_some_and(|items|items.iter().any(|item|matches!(item["error"]["code"].as_str(),Some("CANCEL_CLEANUP_FAILED"|"PLAYBACK_OPEN_TIMEOUT"))))
}
#[tauri::command]
fn discover()->Result<Vec<Value>,String> {engine_manager::discover()}
#[tauri::command]
async fn validate(engine:String,request:Value)->Result<Value,String> {tauri::async_runtime::spawn_blocking(move||EngineManager::validate(&engine,request)).await.map_err(|e|e.to_string())?}
#[tauri::command]
async fn start(app:tauri::AppHandle,engine:String,request:Value)->Result<Value,String> {
    tauri::async_runtime::spawn_blocking(move||{
        let d=app.state::<Desktop>();
        let _control=d.audio_control.lock().unwrap();
        if speech_blocks_vc(&d.speech.lock().unwrap().snapshot()) { return Err("請先完成 TTS Queue 並確認取消清理；必要時 Exit 後重新啟動".into()); }
        *d.last.lock().unwrap()=Some((engine.clone(),request.clone()));
        let handle=app.clone(); let result=d.engine.lock().unwrap().start(&engine,request,Arc::new(move|e|{let _=handle.emit("engine-event",e);})); result
    }).await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn stop(app:tauri::AppHandle)->Result<Value,String> {tauri::async_runtime::spawn_blocking(move||app.state::<Desktop>().engine.lock().unwrap().stop()).await.map_err(|e|e.to_string())?}
#[tauri::command]
fn status(d:tauri::State<Desktop>)->Value {d.engine.lock().unwrap().status()}
#[tauri::command]
fn logs(d:tauri::State<Desktop>)->Vec<Value> {d.engine.lock().unwrap().logs()}
#[tauri::command]
async fn speech_status(app:tauri::AppHandle)->Result<Value,String> {
    tauri::async_runtime::spawn_blocking(move|| {
        let handle=app.clone();
        app.state::<Desktop>().speech.lock().unwrap().status(Arc::new(move|event|{let _=handle.emit("speech-event",event);}))
    }).await.map_err(|e|e.to_string())?
}
#[tauri::command]
async fn speech_action(app:tauri::AppHandle,action:Value)->Result<Value,String> {
    tauri::async_runtime::spawn_blocking(move|| {
        let d=app.state::<Desktop>();
        let _control=d.audio_control.lock().unwrap();
        if action["action"]=="submit" && d.engine.lock().unwrap().status()["service_alive"]==true { return Err("請先停止受管制的 VC runner，再發送 TTS；Mic STT 不受此限制".into()); }
        let handle=app.clone();
        let result=d.speech.lock().unwrap().action(action,Arc::new(move|event|{let _=handle.emit("speech-event",event);}));result
    }).await.map_err(|e|e.to_string())?
}
#[tauri::command]
fn shell_status(d:tauri::State<Desktop>)->Shell {d.shell.lock().unwrap().clone()}
#[tauri::command]
fn window_status(app:tauri::AppHandle)->Result<Value,String> {
    let w=app.get_webview_window("main").ok_or("主視窗不存在")?;
    #[cfg(windows)]
    let extended_style=unsafe {windows_sys::Win32::UI::WindowsAndMessaging::GetWindowLongPtrW(w.hwnd().map_err(|e|e.to_string())?.0 as _,windows_sys::Win32::UI::WindowsAndMessaging::GWL_EXSTYLE)};
    #[cfg(not(windows))]
    let extended_style=0isize;
    Ok(json!({"size":w.inner_size().map_err(|e|e.to_string())?,"position":w.outer_position().map_err(|e|e.to_string())?,"scale_factor":w.scale_factor().map_err(|e|e.to_string())?,"visible":w.is_visible().map_err(|e|e.to_string())?,"always_on_top":w.is_always_on_top().map_err(|e|e.to_string())?,"decorated":w.is_decorated().map_err(|e|e.to_string())?,"extended_style":extended_style,"native_click_through":extended_style&0x20!=0,"tray_registered":app.tray_by_id("aethertune").is_some()}))
}
#[tauri::command]
fn set_shell(app:tauri::AppHandle, shell:Shell)->Result<(),String> {
    let d=app.state::<Desktop>(); let mut current=d.shell.lock().unwrap();
    // 驗證新的快捷鍵後再替換；失敗恢復舊註冊，保留 click-through 逃生入口。
    if shell.visibility_hotkey==shell.voice_hotkey { return Err("兩組快捷鍵不可相同".into()); }
    let _: tauri_plugin_global_shortcut::Shortcut=shell.visibility_hotkey.parse().map_err(|e|format!("{e}"))?;
    let _: tauri_plugin_global_shortcut::Shortcut=shell.voice_hotkey.parse().map_err(|e|format!("{e}"))?;
    let changed=shell.visibility_hotkey!=current.visibility_hotkey || shell.voice_hotkey!=current.voice_hotkey;
    if changed {
        app.global_shortcut().unregister_all().map_err(|e|e.to_string())?;
        if let Err(e)=register_hotkeys(&app,&shell) {
            let _=app.global_shortcut().unregister_all(); let _=register_hotkeys(&app,&current); return Err(e);
        }
    }
    if let Err(e)=apply_shell(&app,&shell) { if changed {let _=app.global_shortcut().unregister_all();let _=register_hotkeys(&app,&current);} let _=apply_shell(&app,&current); return Err(e); }
    let folder=engine_manager::root().join("artifacts/desktop"); fs::create_dir_all(&folder).map_err(|e|e.to_string())?;
    // 重啟時永不恢復 click-through，以免視窗失去控制。
    let mut stored=shell.clone(); stored.click_through=false; stored.quick_input=false;
    fs::write(folder.join("shell.json"),serde_json::to_vec_pretty(&stored).unwrap()).map_err(|e|e.to_string())?;
    *current=shell;record_action("shell:apply"); Ok(())
}
#[tauri::command]
fn drag(app:tauri::AppHandle)->Result<(),String> {if !app.state::<Desktop>().shell.lock().unwrap().locked {app.get_webview_window("main").unwrap().start_dragging().map_err(|e|e.to_string())?;} Ok(())}
#[tauri::command]
fn move_window(app:tauri::AppHandle,x:i32,y:i32)->Result<(),String> {
    if !app.state::<Desktop>().shell.lock().unwrap().locked {
        app.get_webview_window("main").ok_or("主視窗不存在")?.set_position(tauri::PhysicalPosition::new(x,y)).map_err(|e|e.to_string())?;
    }
    Ok(())
}
#[tauri::command]
fn hide(app:tauri::AppHandle)->Result<(),String> {let result=app.get_webview_window("main").unwrap().hide().map_err(|e|e.to_string());if result.is_ok(){record_action("window:hide");}result}
#[tauri::command]
fn exit(app:tauri::AppHandle) {app.exit(0);}
fn register_hotkeys(app:&tauri::AppHandle,shell:&Shell)->Result<(),String> {
    app.global_shortcut().on_shortcut(shell.visibility_hotkey.as_str(),|app,_,event|if event.state==ShortcutState::Pressed {
        record_action("hotkey:visibility");
        if let Some(w)=app.get_webview_window("main") {if w.is_visible().unwrap_or(false) && !app.state::<Desktop>().shell.lock().unwrap().click_through {let _=w.hide();} else {reveal(app,None);}}
    }).map_err(|e|e.to_string())?;
    app.global_shortcut().on_shortcut(shell.voice_hotkey.as_str(),|app,_,event|if event.state==ShortcutState::Pressed {record_action("hotkey:voice");let handle=app.clone();std::thread::spawn(move||toggle_voice(&handle));}).map_err(|e|e.to_string())?;
    Ok(())
}
fn main() {
    let mut shell:Shell=fs::read(engine_manager::root().join("artifacts/desktop/shell.json")).ok().and_then(|s|serde_json::from_slice(&s).ok()).unwrap_or_default(); shell.click_through=false;
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app,_,_|reveal(app,None)))
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .manage(Desktop{engine:Mutex::new(EngineManager::new()),speech:Mutex::new(SpeechManager::default()),audio_control:Mutex::new(()),shell:Mutex::new(shell),last:Mutex::new(None)})
        .invoke_handler(tauri::generate_handler![discover,validate,start,stop,status,logs,speech_status,speech_action,shell_status,window_status,set_shell,drag,move_window,hide,exit])
        .setup(|app| {
            let handle=app.handle(); let shell=app.state::<Desktop>().shell.lock().unwrap().clone();
            register_hotkeys(handle,&shell)?; apply_shell(handle,&shell)?;
            let open=MenuItem::with_id(app,"open","Open AetherTune",true,None::<&str>)?;
            let overlay=MenuItem::with_id(app,"overlay","Show Overlay",true,None::<&str>)?;
            let toggle=MenuItem::with_id(app,"toggle","Start / Stop runner (TEMPORARY)",true,None::<&str>)?;
            let recover=MenuItem::with_id(app,"recover","Disable click-through",true,None::<&str>)?;
            let quit=MenuItem::with_id(app,"exit","Exit",true,None::<&str>)?;
            let menu=Menu::with_items(app,&[&open,&overlay,&toggle,&recover,&quit])?;
            let icon=tauri::image::Image::new_owned([45u8,212,191,255].repeat(32*32),32,32);
            TrayIconBuilder::with_id("aethertune").icon(icon).tooltip("AetherTune — audio WAITING").menu(&menu).show_menu_on_left_click(false)
                .on_menu_event(|app,e|{record_action(&format!("tray:{}",e.id.as_ref()));match e.id.as_ref(){"open"=>reveal(app,Some("full")),"overlay"=>reveal(app,Some("compact")),"recover"=>reveal(app,None),"toggle"=>{let handle=app.clone();std::thread::spawn(move||toggle_voice(&handle));},"exit"=>app.exit(0),_=>{}}})
                .on_tray_icon_event(|tray,event|if matches!(event,TrayIconEvent::Click{button:MouseButton::Left,button_state:MouseButtonState::Up,..}) {record_action("tray:left_click");reveal(tray.app_handle(),None);})
                .build(app)?;
            start_diagnostics(handle.clone());
            Ok(())
        })
        .on_window_event(|w,event|if let tauri::WindowEvent::CloseRequested{api,..}=event {api.prevent_close();let _=w.hide();})
        .build(tauri::generate_context!()).expect("AetherTune desktop 初始化失敗")
        .run(|app,event|if matches!(event,tauri::RunEvent::ExitRequested{..}|tauri::RunEvent::Exit) {let _=app.state::<Desktop>().speech.lock().unwrap().shutdown();let _=app.state::<Desktop>().engine.lock().unwrap().stop();});
}
