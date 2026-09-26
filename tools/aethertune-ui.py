"""AetherTune 輕量 Windows 控制 UI；標準庫 Tkinter，backend 各用隔離 Python。"""
from __future__ import annotations

import hashlib
import json
import math
import os
import queue
import shutil
import subprocess
import threading
import time
import traceback
import uuid
import wave
from collections import Counter
from pathlib import Path
from tkinter import filedialog, scrolledtext, ttk
import tkinter as tk


ROOT = Path(__file__).resolve().parents[1]
UI_ARTIFACTS = ROOT / "artifacts" / "ui"
PREFERENCES_PATH = UI_ARTIFACTS / "settings.json"
PYTHONS = {
    "seed": ROOT / "tools" / "venvs" / "seed-vc" / "Scripts" / "python.exe",
    "mean": ROOT / "tools" / "venvs" / "meanvc2" / "Scripts" / "python.exe",
    "xvc": ROOT / "tools" / "venvs" / "xvc" / "Scripts" / "python.exe",
}
BACKENDS = {
    "Seed-VC realtime-tiny（官方 GUI）": "seed",
    "MeanVC2（WAV）": "mean",
    "X-VC（WAV）": "xvc",
}
SEED_DEFAULTS = {
    "diffusion_steps": 10,
    "inference_cfg_rate": 0.7,
    "max_prompt_length": 3,
    "block_time": 0.30,
    "crossfade_length": 0.04,
    "extra_time_ce": 5.0,
    "extra_time": 0.5,
    "extra_time_right": 0.02,
}
# 數值範圍與步進沿用官方 GUI 欄位；extra_time 是 DiT extra time。
SEED_BOUNDS = {
    "diffusion_steps": (1, 30, 1, int),
    "inference_cfg_rate": (0, 1, 0.1, float),
    "max_prompt_length": (1, 20, 0.5, float),
    "block_time": (0.04, 3, 0.02, float),
    "crossfade_length": (0.02, 0.50, 0.02, float),
    "extra_time_ce": (0.5, 10, 0.1, float),
    "extra_time": (0.5, 10, 0.1, float),
    "extra_time_right": (0.02, 10, 0.02, float),
}
XVC_DEFAULTS = {"current": 160, "chunk": 2400, "future": 80, "smooth": 20}


def _resolved(path_text: str) -> Path:
    return Path(path_text).expanduser().resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class App:
    """可由外部 Tk 腳本用 App(root=None) 建立；提供 vars/widgets 與工作狀態。"""

    def __init__(self, root: tk.Tk | None = None):
        self.root = root or tk.Tk()
        self.root.title("AetherTune 控制台")
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = min(1000, max(860, screen_width - 40))
        # winfo_screenheight 包含 Windows 工作列；多留 180px 給工作列與標題列。
        window_height = min(740, max(600, screen_height - 180))
        self.window_width = window_width
        self.root.geometry(f"{window_width}x{window_height}+{max(0, (screen_width-window_width)//2)}+30")
        self.root.minsize(min(880, window_width), min(620, window_height))
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.ui_thread_id = threading.get_ident()

        self.events: queue.Queue = queue.Queue()
        self.process: subprocess.Popen | None = None
        self.enum_process: subprocess.Popen | None = None
        self.audio_inventory: dict | None = None
        self.device_by_label: dict[str, dict[str, dict]] = {"input": {}, "output": {}}
        self.last_result: dict | None = None
        self.last_process_returncode: int | None = None
        self.run_directory: Path | None = None
        self.output_path: Path | None = None
        self.result_directory: Path | None = None
        self.stop_requested = False
        self.close_pending = False
        self.closed = False
        self._poll_after_id = None

        preferences = self._read_preferences()
        default_backend = next(iter(BACKENDS))
        demo_source = ROOT / "dataset" / "reference-voices" / "voice-male-m1.wav"
        demo_reference = ROOT / "dataset" / "reference-voices" / "voice-female-f1.wav"
        self.vars = {
            "backend": tk.StringVar(value=preferences.get("backend", default_backend)),
            "source": tk.StringVar(value=preferences.get("source", str(demo_source) if demo_source.is_file() else "")),
            "reference": tk.StringVar(value=preferences.get("reference", str(demo_reference) if demo_reference.is_file() else "")),
            "host_api": tk.StringVar(value=preferences.get("host_api", "")),
            "input_device": tk.StringVar(value=preferences.get("input_device", "")),
            "output_device": tk.StringVar(value=preferences.get("output_device", "")),
            "mean_model": tk.StringVar(value=preferences.get("mean_model", "40ms")),
            "x_current": tk.StringVar(value=str(preferences.get("x_current", XVC_DEFAULTS["current"]))),
            "x_chunk": tk.StringVar(value=str(preferences.get("x_chunk", XVC_DEFAULTS["chunk"]))),
            "x_future": tk.StringVar(value=str(preferences.get("x_future", XVC_DEFAULTS["future"]))),
            "x_smooth": tk.StringVar(value=str(preferences.get("x_smooth", XVC_DEFAULTS["smooth"]))),
        }
        for name, value in SEED_DEFAULTS.items():
            self.vars[name] = tk.StringVar(value=str(preferences.get(name, value)))

        self.status_var = tk.StringVar(value="準備中：讀取 Seed-VC 音訊裝置。")
        self.info_var = tk.StringVar(value="")
        self.widgets: dict[str, tk.Widget] = {}
        self._build_widgets()
        self._refresh_form()
        self._start_device_inventory()
        self._poll_after_id = self.root.after(80, self._poll_events)

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @property
    def is_busy(self) -> bool:
        return self.is_running

    def _read_preferences(self) -> dict:
        try:
            data = json.loads(PREFERENCES_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            self._preference_error = f"讀取 UI 偏好失敗，使用預設值：{exc}"
            return {}

    def _build_widgets(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        body = ttk.Frame(self.root, padding=12)
        body.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(8, weight=1)

        ttk.Label(body, text="AetherTune 控制台", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            body,
            text="Seed-VC 會開啟官方即時 GUI；MeanVC2 與 X-VC 在此提供 WAV 檔案轉換。",
            wraplength=940,
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))

        backend_row = ttk.Frame(body)
        backend_row.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(backend_row, text="Backend", width=16).pack(side="left")
        backend = ttk.Combobox(backend_row, textvariable=self.vars["backend"], values=list(BACKENDS), state="readonly")
        backend.pack(side="left", fill="x", expand=True)
        backend.bind("<<ComboboxSelected>>", lambda _event: self._refresh_form())
        self.widgets["backend"] = backend

        self.source_frame = ttk.LabelFrame(body, text="音訊檔案", padding=8)
        self.source_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self.source_frame.columnconfigure(1, weight=1)
        self._make_file_row(self.source_frame, 0, "來源 WAV", "source")
        self._make_file_row(self.source_frame, 1, "Reference WAV", "reference")

        self.device_frame = ttk.LabelFrame(body, text="Seed-VC 音訊裝置", padding=8)
        self.device_frame.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        self.device_frame.columnconfigure(1, weight=1)
        ttk.Label(self.device_frame, text="Host API", width=18).grid(row=0, column=0, sticky="w", padx=(0, 6), pady=3)
        host = ttk.Combobox(self.device_frame, textvariable=self.vars["host_api"], state="readonly")
        host.grid(row=0, column=1, sticky="ew", pady=3)
        host.bind("<<ComboboxSelected>>", lambda _event: self._update_device_choices())
        self.widgets["host_api"] = host
        ttk.Label(self.device_frame, text="輸入裝置", width=18).grid(row=1, column=0, sticky="w", padx=(0, 6), pady=3)
        input_device = ttk.Combobox(self.device_frame, textvariable=self.vars["input_device"], state="readonly")
        input_device.grid(row=1, column=1, sticky="ew", pady=3)
        self.widgets["input_device"] = input_device
        ttk.Label(self.device_frame, text="輸出裝置", width=18).grid(row=2, column=0, sticky="w", padx=(0, 6), pady=3)
        output_device = ttk.Combobox(self.device_frame, textvariable=self.vars["output_device"], state="readonly")
        output_device.grid(row=2, column=1, sticky="ew", pady=3)
        self.widgets["output_device"] = output_device
        ttk.Button(self.device_frame, text="重新讀取裝置", command=self._start_device_inventory).grid(
            row=0, column=2, rowspan=3, padx=(10, 0), sticky="ns"
        )

        self.seed_frame = ttk.LabelFrame(body, text="Seed-VC 進階參數", padding=8)
        self.seed_frame.grid(row=5, column=0, sticky="ew", pady=(0, 8))
        self.seed_frame.columnconfigure(1, weight=1)
        self.seed_frame.columnconfigure(3, weight=1)
        seed_items = [
            ("diffusion_steps", "Diffusion steps"),
            ("inference_cfg_rate", "Inference CFG rate"),
            ("max_prompt_length", "Max prompt length"),
            ("block_time", "Block time (s)"),
            ("crossfade_length", "Crossfade length (s)"),
            ("extra_time_ce", "Extra time CE"),
            ("extra_time", "Extra time (DiT)"),
            ("extra_time_right", "Extra time right (s)"),
        ]
        for index, (name, label) in enumerate(seed_items):
            row, pair = divmod(index, 2)
            col = pair * 2
            low, high, step, _cast = SEED_BOUNDS[name]
            ttk.Label(self.seed_frame, text=label, width=22).grid(row=row, column=col, sticky="w", padx=(0, 6), pady=3)
            field = ttk.Spinbox(
                self.seed_frame,
                textvariable=self.vars[name],
                from_=low,
                to=high,
                increment=step,
                width=14,
            )
            field.grid(row=row, column=col + 1, sticky="ew", pady=3)
            self.widgets[name] = field

        self.mean_frame = ttk.LabelFrame(body, text="MeanVC2 參數", padding=8)
        self.mean_frame.grid(row=6, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(self.mean_frame, text="模型速度").pack(side="left", padx=(0, 8))
        mean_model = ttk.Combobox(self.mean_frame, textvariable=self.vars["mean_model"], values=("40ms", "120ms"), state="readonly", width=12)
        mean_model.pack(side="left")
        self.widgets["mean_model"] = mean_model

        self.xvc_frame = ttk.LabelFrame(body, text="X-VC 參數（檔案轉換）", padding=8)
        self.xvc_frame.grid(row=6, column=0, sticky="ew", pady=(0, 8))
        x_rows = (
            ("x_current", "Current", ("0", "160")),
            ("x_chunk", "Chunk", None),
            ("x_future", "Future", None),
            ("x_smooth", "Smooth", None),
        )
        for index, (name, label, choices) in enumerate(x_rows):
            col = index * 2
            ttk.Label(self.xvc_frame, text=f"{label} (ms)").grid(row=0, column=col, sticky="w", padx=(0, 5))
            field = (ttk.Combobox(self.xvc_frame, textvariable=self.vars[name], values=choices, state="readonly", width=8)
                     if choices else ttk.Entry(self.xvc_frame, textvariable=self.vars[name], width=10))
            field.grid(row=0, column=col + 1, sticky="w", padx=(0, 12))
            self.widgets[name] = field

        ttk.Label(body, textvariable=self.info_var, foreground="#444", wraplength=940).grid(
            row=7, column=0, sticky="ew", pady=(0, 8)
        )
        log_frame = ttk.LabelFrame(body, text="執行日誌", padding=6)
        log_frame.grid(row=8, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=4, wrap="word", state="disabled", font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.widgets["log"] = self.log_text

        footer = ttk.Frame(body)
        footer.grid(row=9, column=0, sticky="ew", pady=(8, 0))
        footer.columnconfigure(0, weight=1)
        status_label = ttk.Label(footer, textvariable=self.status_var, wraplength=max(500, self.window_width - 40), justify="left")
        status_label.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        footer.bind("<Configure>", lambda event: status_label.configure(wraplength=max(400, event.width - 12)))
        actions = ttk.Frame(footer)
        actions.grid(row=1, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        self.widgets["start"] = ttk.Button(actions, text="啟動", command=self.start)
        self.widgets["start"].grid(row=0, column=1, padx=(8, 0))
        self.widgets["stop"] = ttk.Button(actions, text="停止", command=self.stop, state="disabled")
        self.widgets["stop"].grid(row=0, column=2, padx=(6, 0))
        self.widgets["open_wav"] = ttk.Button(actions, text="開啟 WAV", command=self.open_wav, state="disabled")
        self.widgets["open_wav"].grid(row=0, column=3, padx=(6, 0))
        self.widgets["open_folder"] = ttk.Button(actions, text="開啟結果資料夾", command=self.open_folder, state="disabled")
        self.widgets["open_folder"].grid(row=0, column=4, padx=(6, 0))
        if hasattr(self, "_preference_error"):
            self._append_log(self._preference_error)

    def _make_file_row(self, parent, row: int, label: str, key: str) -> None:
        label_widget = ttk.Label(parent, text=label, width=18)
        label_widget.grid(row=row, column=0, sticky="w", padx=(0, 6), pady=3)
        field = ttk.Entry(parent, textvariable=self.vars[key])
        field.grid(row=row, column=1, sticky="ew", pady=3)
        self.widgets[f"{key}_label"] = label_widget
        self.widgets[f"{key}_entry"] = field
        button = ttk.Button(parent, text="選擇…", command=lambda v=self.vars[key]: self._browse_wav(v))
        button.grid(row=row, column=2, padx=(8, 0), pady=3)
        self.widgets[f"{key}_browse"] = button

    def _browse_wav(self, variable: tk.StringVar) -> None:
        value = filedialog.askopenfilename(
            parent=self.root,
            title="選擇 WAV 音訊",
            filetypes=(("WAV 音訊", "*.wav"), ("所有檔案", "*.*")),
        )
        if value:
            variable.set(value)

    def _append_log(self, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{stamp}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def log(self, message: str) -> None:
        """供外部 Tk 測試腳本記錄一筆日誌。"""
        self._append_log(str(message))

    def _refresh_form(self) -> None:
        backend = BACKENDS.get(self.vars["backend"].get(), "seed")
        show_source = backend != "seed"
        source_widgets = (self.widgets["source_label"], self.widgets["source_entry"], self.widgets["source_browse"])
        for widget in source_widgets:
            if show_source:
                widget.grid()
            else:
                widget.grid_remove()
        reference_row = 1 if show_source else 0
        for key in ("reference_label", "reference_entry", "reference_browse"):
            self.widgets[key].grid_configure(row=reference_row)
        if backend == "seed":
            self.source_frame.grid()
            self.device_frame.grid()
            self.seed_frame.grid()
            self.mean_frame.grid_remove()
            self.xvc_frame.grid_remove()
            self.info_var.set("Seed-VC 即時流程：確認官方視窗參數後按 Start VC；停止時先按官方 Stop，再關閉官方視窗。")
        elif backend == "mean":
            self.source_frame.grid()
            self.device_frame.grid_remove()
            self.seed_frame.grid_remove()
            self.mean_frame.grid()
            self.xvc_frame.grid_remove()
            self.info_var.set("MeanVC2 只執行 WAV 檔案轉換；本 UI 不啟動麥克風模式。")
        else:
            self.source_frame.grid()
            self.device_frame.grid_remove()
            self.seed_frame.grid_remove()
            self.mean_frame.grid_remove()
            self.xvc_frame.grid()
            self.info_var.set("X-VC 只執行 WAV 檔案轉換；streaming 視窗需滿足 current + future + smooth <= chunk。")

    def _start_device_inventory(self) -> None:
        if self.enum_process is not None and self.enum_process.poll() is None:
            self._append_log("音訊裝置列舉仍在執行。")
            return
        python = PYTHONS["seed"]
        if not python.is_file():
            report = f"WAITING：找不到 Seed-VC Python：{python}"
            if not self.is_running and self.last_result is None:
                self.status_var.set(report)
            self._append_log(report)
            return
        code = (
            "import json,sounddevice as sd; "
            "apis=[{'index':i,'name':str(x['name'])} for i,x in enumerate(sd.query_hostapis())]; "
            "devices=[{'index':i,'name':str(x['name']),'hostapi':int(x['hostapi']),"
            "'max_input_channels':int(x['max_input_channels']),'max_output_channels':int(x['max_output_channels'])} "
            "for i,x in enumerate(sd.query_devices())]; "
            "defaults=[None if x is None else int(x) for x in sd.default.device]; "
            "print(json.dumps({'hostapis':apis,'devices':devices,'defaults':defaults},ensure_ascii=True))"
        )
        try:
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            proc = subprocess.Popen(
                [str(python), "-c", code], cwd=str(ROOT), stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
                text=True, encoding="utf-8", errors="replace", env=env,
            )
        except OSError as exc:
            report = f"BLOCKED：無法列舉 Seed-VC 音訊裝置：{exc}"
            if not self.is_running and self.last_result is None:
                self.status_var.set(report)
            self._append_log(report)
            return
        self.enum_process = proc
        if not self.is_running and self.last_result is None:
            self.status_var.set("準備中：正在讀取 Seed-VC 音訊裝置。")
        threading.Thread(target=self._read_device_inventory, args=(proc,), daemon=True).start()

    def _read_device_inventory(self, proc: subprocess.Popen) -> None:
        try:
            stdout, stderr = proc.communicate(timeout=35)
        except subprocess.TimeoutExpired:
            self._kill_process_tree(proc, "音訊裝置列舉逾時")
            stdout, stderr = proc.communicate()
            self.events.put(("devices_error", proc, f"逾時。{stderr.strip()}"))
            return
        if proc.returncode != 0:
            self.events.put(("devices_error", proc, stderr.strip() or stdout.strip() or f"exit {proc.returncode}"))
            return
        try:
            lines = [line for line in stdout.splitlines() if line.strip()]
            payload = json.loads(lines[-1])
            if not isinstance(payload, dict) or not isinstance(payload.get("devices"), list):
                raise ValueError("sounddevice 回傳格式不完整")
            self.events.put(("devices", proc, payload))
        except (IndexError, json.JSONDecodeError, ValueError) as exc:
            self.events.put(("devices_error", proc, f"無法解析 sounddevice JSON：{exc}; {stdout.strip()}"))

    def _accept_device_inventory(self, payload: dict) -> None:
        apis = payload.get("hostapis", [])
        api_counts = Counter(str(api.get("name", "")) for api in apis)
        api_names = {int(api["index"]): str(api["name"]) for api in apis
                     if api.get("name") and api_counts[str(api.get("name"))] == 1}
        devices = []
        for row in payload.get("devices", []):
            try:
                devices.append({
                    "index": int(row["index"]), "name": str(row["name"]),
                    "hostapi": int(row["hostapi"]), "hostapi_name": api_names[int(row["hostapi"])],
                    "max_input_channels": int(row["max_input_channels"]),
                    "max_output_channels": int(row["max_output_channels"]),
                })
            except (KeyError, TypeError, ValueError):
                continue
        valid_apis = []
        for api_name in sorted(set(api_names.values())):
            api_devices = [row for row in devices if row["hostapi_name"] == api_name]
            inputs = [row for row in api_devices if row["max_input_channels"] > 0]
            outputs = [row for row in api_devices if row["max_output_channels"] > 0]
            if any(n == 1 for n in Counter(row["name"] for row in inputs).values()) and any(
                n == 1 for n in Counter(row["name"] for row in outputs).values()
            ):
                valid_apis.append(api_name)
        defaults = payload.get("defaults", [-1, -1])
        default_api = None
        try:
            default_input = next(row for row in devices if row["index"] == defaults[0])
            default_output = next(row for row in devices if row["index"] == defaults[1])
            if default_input["hostapi_name"] == default_output["hostapi_name"]:
                default_api = default_input["hostapi_name"]
        except (IndexError, StopIteration, TypeError):
            pass
        self.audio_inventory = {"devices": devices, "defaults": defaults}
        host_widget = self.widgets["host_api"]
        host_widget.configure(values=valid_apis)
        selected = self.vars["host_api"].get()
        if selected not in valid_apis:
            selected = default_api if default_api in valid_apis else (valid_apis[0] if valid_apis else "")
            self.vars["host_api"].set(selected)
        self._update_device_choices()
        status = (f"PASS：讀取 {len(devices)} 個端點；可選 Host API {len(valid_apis)} 個。"
                  if valid_apis else "WAITING：沒有同一 Host API 下可唯一解析的輸入與輸出裝置。")
        if not self.is_running and self.last_result is None:
            self.status_var.set(status)
        self._append_log(status)

    def _update_device_choices(self) -> None:
        if not self.audio_inventory:
            return
        api_name = self.vars["host_api"].get()
        for direction, channel in (("input", "max_input_channels"), ("output", "max_output_channels")):
            rows = [row for row in self.audio_inventory["devices"]
                    if row["hostapi_name"] == api_name and row[channel] > 0]
            counts = Counter(row["name"] for row in rows)
            unique_rows = [row for row in rows if counts[row["name"]] == 1]
            labels = [f"{row['name']}  [index {row['index']}]" for row in unique_rows]
            mapping = dict(zip(labels, unique_rows))
            self.device_by_label[direction] = mapping
            widget = self.widgets[f"{direction}_device"]
            widget.configure(values=labels)
            if self.vars[f"{direction}_device"].get() not in mapping:
                default_index = self.audio_inventory.get("defaults", [-1, -1])[0 if direction == "input" else 1]
                default = next((row for row in unique_rows if row["index"] == default_index), None)
                label = f"{default['name']}  [index {default['index']}]" if default else (labels[0] if labels else "")
                self.vars[f"{direction}_device"].set(label)

    def _save_preferences(self) -> None:
        data = {name: variable.get() for name, variable in self.vars.items()}
        try:
            UI_ARTIFACTS.mkdir(parents=True, exist_ok=True)
            temporary = PREFERENCES_PATH.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporary, PREFERENCES_PATH)
        except OSError as exc:
            self._log_any_thread(f"保存 UI 偏好失敗：{exc}")

    def _validate_wav(self, label: str, value: str) -> Path:
        if not value.strip():
            raise ValueError(f"請選擇{label} WAV。")
        path = _resolved(value)
        if path.suffix.lower() != ".wav":
            raise ValueError(f"{label} 檔案必須是 .wav：{path}")
        if not path.is_file():
            raise ValueError(f"找不到{label}檔案：{path}")
        return path

    def _parse_seed_settings(self) -> dict:
        values = {}
        for name, (minimum, maximum, step, cast) in SEED_BOUNDS.items():
            raw = self.vars[name].get().strip()
            try:
                value = cast(raw)
            except (TypeError, ValueError):
                raise ValueError(f"Seed-VC 參數 {name} 必須是數值。")
            aligned = (float(value) - minimum) / step
            if (not math.isfinite(float(value)) or value < minimum or value > maximum
                    or not math.isclose(aligned, round(aligned), rel_tol=0, abs_tol=1e-7)):
                raise ValueError(f"Seed-VC 參數 {name} 範圍為 {minimum} 到 {maximum}，步進為 {step}。")
            values[name] = value
        if values["crossfade_length"] > values["block_time"]:
            raise ValueError("Seed-VC crossfade_length 必須小於或等於 block_time。")
        if values["extra_time_ce"] < values["extra_time"]:
            raise ValueError("Seed-VC extra_time_ce 必須大於或等於 extra_time（DiT）。")
        return values

    def _parse_xvc_settings(self) -> dict:
        try:
            values = {key: int(self.vars[f"x_{key}"].get()) for key in XVC_DEFAULTS}
        except ValueError:
            raise ValueError("X-VC current、chunk、future、smooth 必須是整數毫秒。")
        if values["current"] not in (0, 160):
            raise ValueError("X-VC current 僅接受 0 或 160 ms。")
        if values["chunk"] <= 0 or values["future"] < 0 or values["smooth"] < 0:
            raise ValueError("X-VC chunk 必須大於 0；future 與 smooth 不可小於 0。")
        if values["current"] > 0 and values["smooth"] > values["current"]:
            raise ValueError("X-VC streaming smooth 不可大於 current，避免 overlap 超過目前輸出區段。")
        if values["current"] > 0 and values["current"] + values["future"] + values["smooth"] > values["chunk"]:
            raise ValueError("X-VC streaming 視窗需滿足 current + future + smooth <= chunk。")
        return values

    def _validate_seed_devices(self) -> tuple[str, str, str]:
        if not self.audio_inventory:
            raise ValueError("Seed-VC 音訊裝置尚未完成列舉；請稍候或重新讀取裝置。")
        host_api = self.vars["host_api"].get().strip()
        input_row = self.device_by_label["input"].get(self.vars["input_device"].get())
        output_row = self.device_by_label["output"].get(self.vars["output_device"].get())
        if not host_api or not input_row or not output_row:
            raise ValueError("請選擇可唯一解析的 Seed-VC Host API、輸入與輸出裝置。")
        if input_row["hostapi_name"] != host_api or output_row["hostapi_name"] != host_api:
            raise ValueError("Seed-VC 輸入與輸出裝置必須位於所選的同一 Host API。")
        return host_api, input_row["name"], output_row["name"]

    def _make_command(self, backend: str, run_dir: Path) -> tuple[list[str], Path | None, Path]:
        python = PYTHONS[backend]
        if not python.is_file():
            raise ValueError(f"找不到 {backend} 隔離 Python：{python}")
        if backend == "seed":
            project_pwsh = ROOT / "tools" / "external" / "powershell" / "pwsh.exe"
            pwsh = str(project_pwsh) if project_pwsh.is_file() else shutil.which("pwsh")
            if not pwsh:
                candidate = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "PowerShell" / "7" / "pwsh.exe"
                pwsh = str(candidate) if candidate.is_file() else None
            if not pwsh:
                raise ValueError("找不到 PowerShell 7（pwsh）；請確認已安裝並加入 PATH。")
            script = ROOT / "tools" / "seed-vc-gui-run.ps1"
            if not script.is_file():
                raise ValueError(f"找不到 Seed-VC launcher：{script}")
            settings = self._parse_seed_settings()
            host_api, input_name, output_name = self._validate_seed_devices()
            settings_path = run_dir / "seed-settings.json"
            settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
            command = [
                pwsh, "-NoProfile", "-File", str(script), "-Python", str(python),
                "-HostApi", host_api, "-InputDeviceName", input_name,
                "-OutputDeviceName", output_name, "-SettingsFile", str(settings_path),
            ]
            reference_value = self.vars["reference"].get().strip()
            if reference_value:
                command.extend(("-ReferenceWav", str(self._validate_wav("Reference", reference_value))))
            else:
                command.append("-ClearReference")
            return command, None, run_dir

        source = self._validate_wav("來源", self.vars["source"].get())
        reference = self._validate_wav("Reference", self.vars["reference"].get())
        if backend == "mean":
            script = ROOT / "tools" / "meanvc2-run.py"
            if not script.is_file():
                raise ValueError(f"找不到 MeanVC2 wrapper：{script}")
            output = run_dir / "output.wav"
            command = [str(python), "-u", str(script), "--source", str(source), "--target", str(reference),
                       "--output", str(output), "--model", self.vars["mean_model"].get()]
        else:
            script = ROOT / "tools" / "xvc-run.py"
            if not script.is_file():
                raise ValueError(f"找不到 X-VC wrapper：{script}")
            settings = self._parse_xvc_settings()
            output = run_dir
            command = [str(python), "-u", str(script), "--source", str(source), "--target", str(reference),
                       "--output-dir", str(output), "--current", str(settings["current"]),
                       "--chunk", str(settings["chunk"]), "--future", str(settings["future"]),
                       "--smooth", str(settings["smooth"])]
        return command, output, run_dir

    def start(self) -> bool:
        """啟動按鈕 callback，也可由測試腳本直接呼叫。"""
        if self.is_running:
            self._append_log("已有工作執行中；GPU 工作一次只允許一項。")
            return False
        self.last_result = None
        self.last_process_returncode = None
        self.output_path = None
        self.result_directory = None
        backend = BACKENDS.get(self.vars["backend"].get())
        if backend is None:
            self._show_error("請選擇有效的 backend。")
            return False
        run_dir = UI_ARTIFACTS / str(uuid.uuid4())
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
            command, expected_output, result_dir = self._make_command(backend, run_dir)
            self._save_preferences()
            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            proc = subprocess.Popen(
                command, cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, shell=False, text=True, encoding="utf-8",
                errors="replace", bufsize=1, env=env,
            )
        except (OSError, ValueError) as exc:
            self._show_error(str(exc))
            return False
        self.process = proc
        self.stop_requested = False
        self.run_directory = run_dir
        self.result_directory = result_dir
        threading.Thread(
            target=self._read_process_output,
            args=(proc, backend, expected_output, result_dir),
            daemon=True,
        ).start()
        self.widgets["start"].configure(state="disabled")
        self.widgets["stop"].configure(state="normal")
        self.widgets["open_wav"].configure(state="disabled")
        self.widgets["open_folder"].configure(state="normal")
        self.status_var.set(f"RUNNING：{self.vars['backend'].get()}；工作目錄 {run_dir.name}")
        self._append_log(f"啟動 PID {proc.pid}：{subprocess.list2cmdline(command)}")
        self._append_log(f"工作目錄：{run_dir}")
        return True

    def _show_error(self, message: str) -> None:
        self.status_var.set(f"BLOCKED：{message}")
        self._append_log(f"BLOCKED：{message}")

    def _read_process_output(self, proc: subprocess.Popen, backend: str,
                             expected_output: Path | None, result_dir: Path) -> None:
        try:
            if proc.stdout is not None:
                for line in proc.stdout:
                    self.events.put(("log", line.rstrip("\r\n")))
        except (OSError, ValueError) as exc:
            self.events.put(("log", f"讀取程序日誌錯誤：{exc}"))
        code = proc.wait()
        if code == 0 and backend in ("mean", "xvc") and expected_output is not None:
            evidence = (expected_output.parent / "output.run-evidence.json" if backend == "mean"
                        else expected_output / "run-evidence.json")
            result = self._inspect_file_result(backend, expected_output if backend == "mean" else None,
                                               evidence, result_dir)
        elif code == 0:
            result = {"status": "WAITING", "message": "Seed-VC 官方 GUI 已正常結束；此即時流程沒有 file-driven WAV evidence。",
                      "wav": None, "directory": str(result_dir)}
        else:
            result = {"status": "STOPPED" if self.stop_requested else "BLOCKED",
                      "message": f"子程序結束碼：{code}" + ("（已停止）" if self.stop_requested else ""),
                      "wav": None, "directory": str(result_dir)}
        self.events.put(("finished", proc, code, result))

    def _inspect_file_result(self, backend: str, expected_output: Path | None,
                             evidence_path: Path, result_dir: Path) -> dict:
        result = {"status": "BLOCKED", "message": "缺少有效輸出 WAV 或 wrapper evidence。",
                  "wav": None, "directory": str(result_dir)}
        try:
            if not evidence_path.is_file():
                result["message"] = f"程序 exit 0，但找不到 wrapper evidence：{evidence_path}"
                return result
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence_backend = "meanvc2" if backend == "mean" else "xvc"
            if evidence.get("status") != "PASS" or evidence.get("backend") != evidence_backend:
                result["message"] = f"wrapper evidence 未通過或 backend 不符：{evidence.get('status')} / {evidence.get('backend')}"
                return result
            outputs = evidence.get("outputs")
            if not isinstance(outputs, list) or len(outputs) != 1 or not isinstance(outputs[0], dict):
                result["message"] = "wrapper evidence 未提供唯一輸出音訊記錄。"
                return result
            metric = outputs[0]
            evidence_output = _resolved(str(metric.get("path", "")))
            if backend == "mean":
                output = expected_output
                if output is None or os.path.normcase(str(evidence_output)) != os.path.normcase(str(output.resolve())):
                    result["message"] = f"evidence WAV 路徑與本次輸出不符：{evidence_output}"
                    return result
            else:
                output = evidence_output
                if (output.suffix.lower() != ".wav"
                        or os.path.normcase(str(output.parent.resolve())) != os.path.normcase(str(result_dir.resolve()))):
                    result["message"] = f"X-VC evidence WAV 不在本次輸出目錄：{output}"
                    return result
            if not output.is_file() or output.stat().st_size < 44:
                result["message"] = f"WAV 不存在或檔案過小：{output}"
                return result
            rms = metric.get("rms")
            seconds = metric.get("seconds")
            rate = metric.get("sample_rate")
            if not metric.get("finite") or not isinstance(rms, (int, float)) or not math.isfinite(float(rms)) or float(rms) <= 1e-4:
                result["message"] = "evidence 音訊 finite/RMS 檢查未通過。"
                return result
            if not isinstance(seconds, (int, float)) or not math.isfinite(float(seconds)) or float(seconds) <= 0.5:
                result["message"] = "evidence 音訊長度未超過 0.5 秒。"
                return result
            if not isinstance(rate, int) or rate <= 0:
                result["message"] = "evidence sample rate 無效。"
                return result
            if str(metric.get("sha256", "")).lower() != _sha256(output).lower():
                result["message"] = "輸出 WAV SHA-256 與 wrapper evidence 不符。"
                return result
            with wave.open(str(output), "rb") as wav:
                actual_seconds = wav.getnframes() / float(wav.getframerate())
                if wav.getnframes() <= 0 or wav.getframerate() != rate or actual_seconds <= 0.5:
                    result["message"] = "WAV header 與 evidence 不符，或音訊長度未超過 0.5 秒。"
                    return result
            result.update({"status": "PASS", "message": f"wrapper evidence 與 WAV 檢查 PASS；{float(seconds):.2f} 秒，{rate} Hz。",
                           "wav": str(output.resolve()), "directory": str(output.parent.resolve()),
                           "seconds": float(seconds), "sample_rate": rate,
                           "sha256": str(metric["sha256"]), "evidence": str(evidence_path.resolve())})
            return result
        except (OSError, ValueError, TypeError, json.JSONDecodeError, wave.Error, ZeroDivisionError) as exc:
            result["message"] = f"讀取 wrapper evidence/WAV 失敗：{exc}"
            return result

    def _poll_events(self) -> None:
        if self.closed:
            return
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "log":
                    self._append_log(event[1])
                elif event[0] == "devices":
                    _, proc, payload = event
                    if self.enum_process is proc:
                        self.enum_process = None
                    self._accept_device_inventory(payload)
                elif event[0] == "devices_error":
                    _, proc, message = event
                    if self.enum_process is proc:
                        self.enum_process = None
                    report = f"WAITING：Seed-VC 裝置列舉失敗：{message}"
                    if not self.is_running and self.last_result is None:
                        self.status_var.set(report)
                    self._append_log(report)
                elif event[0] == "finished":
                    _, proc, code, result = event
                    if self.process is proc:
                        self.process = None
                        self.last_process_returncode = code
                        self.last_result = result
                        self.output_path = Path(result["wav"]) if result.get("wav") else None
                        self.result_directory = Path(result["directory"]) if result.get("directory") else self.run_directory
                        self.widgets["start"].configure(state="normal")
                        self.widgets["stop"].configure(state="disabled")
                        self.widgets["open_wav"].configure(state="normal" if self.output_path else "disabled")
                        self.widgets["open_folder"].configure(state="normal" if self.result_directory else "disabled")
                        self.status_var.set(f"{result['status']}：{result['message']}")
                        self._append_log(f"程序完成，exit {code}；{self.status_var.get()}")
                        self._finish_close_if_ready()
        except queue.Empty:
            pass
        if not self.closed:
            self._poll_after_id = self.root.after(80, self._poll_events)

    def _log_any_thread(self, message: str) -> None:
        if threading.get_ident() == self.ui_thread_id:
            self._append_log(message)
        else:
            self.events.put(("log", message))

    def _kill_process_tree(self, proc: subprocess.Popen, description: str) -> bool:
        # 只在 poll() 確認仍活著時使用 taskkill，避免碰到已回收 PID。
        if proc.poll() is not None:
            return True
        if os.name != "nt":
            self._log_any_thread(f"{description}：taskkill 僅支援 Windows。")
            return False
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"], cwd=str(ROOT),
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                shell=False, text=True, encoding="utf-8", errors="replace", timeout=15,
            )
            if result.stdout.strip():
                self._log_any_thread(result.stdout.strip())
            if proc.poll() is None and result.returncode != 0:
                self._log_any_thread(f"{description}失敗，taskkill exit {result.returncode}。")
                return False
            self._log_any_thread(f"{description}：已要求清理 PID {proc.pid} 的程序樹。")
            return True
        except (OSError, subprocess.TimeoutExpired) as exc:
            self._log_any_thread(f"{description}失敗：{exc}")
            return False

    def stop(self) -> bool:
        """停止按鈕 callback；只清理本 UI 啟動且仍存活的程序樹。"""
        proc = self.process
        if proc is None or proc.poll() is not None:
            self._append_log("目前沒有執行中的 backend 工作。")
            self.widgets["stop"].configure(state="disabled")
            return False
        self.stop_requested = True
        self.status_var.set(f"停止中：清理 PID {proc.pid} 的程序樹。")
        stopped = self._kill_process_tree(proc, "停止 backend 工作")
        if stopped:
            self.widgets["stop"].configure(state="disabled")
            self._append_log("已送出停止要求；等待輸出管線結束。")
        return stopped

    def open_wav(self) -> bool:
        if self.output_path is None or not self.output_path.is_file():
            self._append_log("目前沒有可開啟的有效 WAV。")
            return False
        try:
            os.startfile(str(self.output_path))
            return True
        except (AttributeError, OSError) as exc:
            self._append_log(f"開啟 WAV 失敗：{exc}")
            return False

    def open_folder(self) -> bool:
        path = self.result_directory or self.run_directory
        if path is None or not path.exists():
            self._append_log("目前沒有可開啟的結果資料夾。")
            return False
        try:
            os.startfile(str(path))
            return True
        except (AttributeError, OSError) as exc:
            self._append_log(f"開啟結果資料夾失敗：{exc}")
            return False

    def _finish_close_if_ready(self) -> None:
        if not self.close_pending:
            return
        if self.is_running:
            self.root.after(120, self._finish_close_if_ready)
            return
        if self.enum_process is not None and self.enum_process.poll() is None:
            self._kill_process_tree(self.enum_process, "關閉時清理音訊列舉程序")
            self.root.after(120, self._finish_close_if_ready)
            return
        self._destroy()

    def close(self) -> None:
        if self.closed:
            return
        self.close_pending = True
        self._save_preferences()
        if self.is_running:
            self.stop()
        if self.enum_process is not None and self.enum_process.poll() is None:
            self._kill_process_tree(self.enum_process, "關閉時清理音訊列舉程序")
        self._finish_close_if_ready()

    def _destroy(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self._poll_after_id is not None:
            try:
                self.root.after_cancel(self._poll_after_id)
            except tk.TclError:
                pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    try:
        app = App()
        app.run()
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
