//! Windows Job Object：先 suspended spawn、納入 job，再 resume，避免衍生程序逃逸。
use std::{io::{BufRead, BufReader, Write}, process::{Child, ChildStdin, Command, Stdio}, sync::{Arc, Mutex}, thread, time::{Duration, Instant}};
use serde_json::Value;
pub type Sink = Arc<dyn Fn(Value) + Send + Sync>;

#[cfg(windows)]
mod job {
    use std::{mem::{size_of, zeroed}, os::windows::{io::AsRawHandle, process::CommandExt}, process::{Child, Command}};
    use windows_sys::Win32::{Foundation::{CloseHandle, HANDLE, INVALID_HANDLE_VALUE}, System::{JobObjects::*, Threading::*, Diagnostics::ToolHelp::*}};
    pub struct Job(HANDLE);
    unsafe impl Send for Job {}
    impl Job {
        pub fn spawn(command: &mut Command) -> Result<(Child, Self), String> {
            unsafe {
                let handle = CreateJobObjectW(std::ptr::null(), std::ptr::null());
                if handle.is_null() { return Err(std::io::Error::last_os_error().to_string()); }
                let job = Self(handle);
                let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = zeroed();
                info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
                if SetInformationJobObject(handle, JobObjectExtendedLimitInformation, &info as *const _ as _, size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32) == 0 { return Err(std::io::Error::last_os_error().to_string()); }
                command.creation_flags(CREATE_SUSPENDED | CREATE_NO_WINDOW);
                let mut child = command.spawn().map_err(|e| e.to_string())?;
                if AssignProcessToJobObject(handle, child.as_raw_handle() as HANDLE) == 0 {
                    let error = std::io::Error::last_os_error().to_string();
                    let _ = child.kill(); let _ = child.wait(); return Err(error);
                }
                let snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
                let mut entry: THREADENTRY32 = zeroed(); entry.dwSize = size_of::<THREADENTRY32>() as u32;
                let mut resumed = false;
                if snapshot != INVALID_HANDLE_VALUE {
                    let mut found = Thread32First(snapshot, &mut entry);
                    while found != 0 {
                        if entry.th32OwnerProcessID == child.id() {
                            let th = OpenThread(THREAD_SUSPEND_RESUME, 0, entry.th32ThreadID);
                            if !th.is_null() { resumed = ResumeThread(th) != u32::MAX; CloseHandle(th); }
                            break;
                        }
                        found = Thread32Next(snapshot, &mut entry);
                    }
                    CloseHandle(snapshot);
                }
                if !resumed { let _ = child.kill(); let _ = child.wait(); return Err("無法 resume 已受管制的子程序".into()); }
                Ok((child, job))
            }
        }
    }
    impl Drop for Job { fn drop(&mut self) { unsafe { CloseHandle(self.0); } } }
}

pub struct Process {
    child: Arc<Mutex<Child>>, input: Option<ChildStdin>,
    threads: Vec<thread::JoinHandle<()>>,
    #[cfg(windows)]
    job: Arc<Mutex<Option<job::Job>>>,
}
impl Process {
    pub fn spawn(mut command: Command, sink: Sink) -> Result<Self, String> {
        command.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped());
        #[cfg(windows)]
        let (mut child, job) = job::Job::spawn(&mut command)?;
        #[cfg(not(windows))]
        let mut child = command.spawn().map_err(|e| e.to_string())?;
        let input = child.stdin.take();
        let stdout = child.stdout.take().ok_or("stdout missing")?;
        let stderr = child.stderr.take().ok_or("stderr missing")?;
        let out_sink = sink.clone();
        let stdout_thread = thread::spawn(move || {
            for line in BufReader::new(stdout).lines() {
                match line {
                    Ok(line) => out_sink(serde_json::from_str(&line).unwrap_or_else(|_| serde_json::json!({"type":"log","stream":"service","message":line}))),
                    Err(e) => { out_sink(serde_json::json!({"type":"error","code":"PROTOCOL_ERROR","message":e.to_string()})); break; }
                }
            }
        });
        let err_sink = sink.clone();
        let stderr_thread = thread::spawn(move || { for line in BufReader::new(stderr).lines().map_while(Result::ok) { err_sink(serde_json::json!({"type":"log","stream":"service-stderr","message":line})); } });
        let shared = Arc::new(Mutex::new(child));
        let watched = shared.clone();
        #[cfg(windows)]
        let job = Arc::new(Mutex::new(Some(job)));
        #[cfg(windows)]
        let watched_job = job.clone();
        let monitor_thread = thread::spawn(move || loop {
            let exit = { watched.lock().unwrap().try_wait() };
            match exit {
                Ok(Some(status)) => {
                    #[cfg(windows)]
                    drop(watched_job.lock().unwrap().take());
                    sink(serde_json::json!({"type":"service_exit","code":status.code()})); break;
                }
                Ok(None) => thread::sleep(Duration::from_millis(100)),
                Err(e) => { sink(serde_json::json!({"type":"error","code":"BACKEND_CRASH","message":e.to_string()})); break; }
            }
        });
        Ok(Self { child: shared, input, threads: vec![stdout_thread, stderr_thread, monitor_thread], #[cfg(windows)] job })
    }
    pub fn id(&self) -> u32 { self.child.lock().unwrap().id() }
    pub fn send(&mut self, command: Value) -> Result<(), String> {
        let input = self.input.as_mut().ok_or("backend stdin closed")?;
        writeln!(input, "{command}").and_then(|_| input.flush()).map_err(|e| e.to_string())
    }
    pub fn alive(&self) -> bool { matches!(self.child.lock().unwrap().try_wait(), Ok(None)) }
    pub fn stop(&mut self) -> Result<(), String> {
        self.stop_with_grace(Duration::from_secs(3))
    }
    pub fn stop_with_grace(&mut self, grace: Duration) -> Result<(), String> {
        let _ = self.send(serde_json::json!({"command":"stop"}));
        let deadline = Instant::now() + grace;
        while self.alive() && Instant::now() < deadline { thread::sleep(Duration::from_millis(50)); }
        // 即使 service 正常結束，仍 close job 清除 upstream 衍生程序。
        #[cfg(windows)]
        drop(self.job.lock().unwrap().take());
        let mut child = self.child.lock().unwrap();
        if child.try_wait().map_err(|e| e.to_string())?.is_none() { child.kill().map_err(|e| e.to_string())?; }
        child.wait().map_err(|e| e.to_string())?;
        drop(child);
        self.input.take();
        for handle in self.threads.drain(..) { let _ = handle.join(); }
        Ok(())
    }
}
impl Drop for Process { fn drop(&mut self) { let _ = self.stop(); } }

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    #[cfg(windows)]
    fn rvc_native_imports_complete() {
        // 與正式服務相同的 Job／隱藏視窗條件；防止 DLL 載入只在一般終端成功。
        let python=crate::engine_manager::root().join(".venv/Scripts/python.exe");
        let (tx,rx)=std::sync::mpsc::channel();
        let mut command=Command::new(python);
        command.args(["-u","-c","import subprocess,sys; p=subprocess.Popen([sys.executable,'-u','-c','import torch; import faiss; print(1,flush=True)'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT); out=p.communicate(timeout=20)[0]; assert p.returncode==0,out; print('{\"type\":\"imports_ready\"}',flush=True)"]);
        let mut process=Process::spawn(command,Arc::new(move|event|{let _=tx.send(event);})).unwrap();
        let event=rx.recv_timeout(Duration::from_secs(30)).expect("RVC native DLL imports timed out");
        assert_eq!(event["type"],"imports_ready");
        process.stop().unwrap();
    }
    #[test]
    fn stop_reaps_owned_process() {
        let mut command = Command::new("cmd.exe"); command.args(["/c", "ping", "-n", "30", "127.0.0.1"]);
        let mut p = Process::spawn(command, Arc::new(|_| {})).unwrap();
        assert!(p.alive()); p.stop().unwrap(); assert!(!p.alive());
    }
    #[test]
    fn detects_crash() {
        let (tx, rx) = std::sync::mpsc::channel();
        let mut command = Command::new("cmd.exe"); command.args(["/c", "exit", "7"]);
        let _p = Process::spawn(command, Arc::new(move |event| { tx.send(event).unwrap(); })).unwrap();
        assert_eq!(rx.recv_timeout(Duration::from_secs(5)).unwrap()["code"], 7);
    }
    #[cfg(windows)]
    fn pid_alive(pid:u32)->bool {
        use windows_sys::Win32::{Foundation::{CloseHandle,WAIT_TIMEOUT},System::Threading::{OpenProcess,WaitForSingleObject,PROCESS_SYNCHRONIZE}};
        unsafe {let handle=OpenProcess(PROCESS_SYNCHRONIZE,0,pid);if handle.is_null(){return false;}let alive=WaitForSingleObject(handle,0)==WAIT_TIMEOUT;CloseHandle(handle);alive}
    }
    #[test]
    #[cfg(windows)]
    fn job_kills_grandchild_on_stop_and_crash() {
        let python=crate::engine_manager::root().join("tools/venvs/seed-vc/Scripts/python.exe");
        for crash in [false,true] {
            let (tx,rx)=std::sync::mpsc::channel();
            let code=format!("import subprocess,sys,time,json; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); print(json.dumps(dict(type='fixture_child',pid=p.pid)),flush=True); time.sleep({}); sys.exit(7)",if crash {1}else{60});
            let mut cmd=Command::new(&python);cmd.args(["-u","-c",&code]);
            let mut p=Process::spawn(cmd,Arc::new(move|event|{let _=tx.send(event);})).unwrap();
            let event=rx.recv_timeout(Duration::from_secs(5)).unwrap();let pid=event["pid"].as_u64().unwrap() as u32;
            assert!(pid_alive(pid));
            if crash {while rx.recv_timeout(Duration::from_secs(5)).unwrap()["type"]!="service_exit"{}}
            else {p.stop().unwrap();}
            let deadline=Instant::now()+Duration::from_secs(3);while pid_alive(pid)&&Instant::now()<deadline {thread::sleep(Duration::from_millis(50));}
            assert!(!pid_alive(pid),"owned grandchild survived cleanup");
        }
    }
}
