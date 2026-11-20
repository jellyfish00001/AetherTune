"""直播 TTS 統一量測工具（各後端共用）。

每個後端腳本只要提供 synth(text) -> 產生 1 維 float32 numpy 音訊 chunk 的 generator，
以及輸出取樣率，其餘（暖機、計時、VRAM 取樣、wav 與 JSON 輸出）都在這裡統一處理。
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import platform
import re
import statistics
import subprocess
import threading
import time
import wave
from pathlib import Path
from typing import Callable, Iterable

import numpy as np

SENTENCES = {
    "short": "大家晚安，謝謝你們來看。",
    "medium": "今天的直播先陪大家聊聊天，等一下再一起來玩新出的遊戲喔。",
    "long": "謝謝小明送的禮物，真的太感動了！今天我們會一路玩到十二點，如果你也喜歡這個遊戲，記得按下追蹤，下次開台就不會錯過囉。",
}

# 同三句的簡體版（逐字對應，長度相同）。CosyVoice2 對繁體字（謝、禮、會、點、遊、戲、記…）常唸錯，用來對照。
SENTENCES_ZHS = {
    "short": "大家晚安，谢谢你们来看。",
    "medium": "今天的直播先陪大家聊聊天，等一下再一起来玩新出的游戏喔。",
    "long": "谢谢小明送的礼物，真的太感动了！今天我们会一路玩到十二点，如果你也喜欢这个游戏，记得按下追踪，下次开台就不会错过啰。",
}
# 只涵蓋本測試句用到的繁→簡字，讓 CER 可以忽略簡繁差異。
T2S = {t: s_ for k in SENTENCES for t, s_ in zip(SENTENCES[k], SENTENCES_ZHS[k]) if t != s_}


def use_simplified():
    global WARMUP_TEXT
    if LISTEN:  # 聽感對照句：用 OpenCC t2s 整句轉（只裝在 CosyVoice2 實驗 venv）
        import opencc  # noqa: PLC0415
        cc = opencc.OpenCC("t2s")
        for k in SENTENCES:
            SENTENCES[k] = cc.convert(SENTENCES[k])
        WARMUP_TEXT = cc.convert(WARMUP_TEXT)
        return
    SENTENCES.update(SENTENCES_ZHS)


# 聽感對照模式（環境變數 LIVE_TTS_SENTENCES 指到 JSON：[{"id": "s1", "text": "..."}]）：
# 數字先轉中文字；開頭用 WARMUP_TEXT 暖機一次（不存檔），之後每句只生成一次。
LISTEN = False
LISTEN_RAW: dict[str, str] = {}
WARMUP_TEXT = "大家好，歡迎來到直播間。"
# GSV-TTS-Lite 常駐暖機：第二句含英文字母，讓第一次載入英文前端（約 5 秒）發生在暖機，不落在第一句中英混合句。
GSV_WARMUP_TEXTS = ("大家好，歡迎來到直播間。", "OK，等一下我們一起來玩 game 吧。")
_ZH_DIGIT = "零一二三四五六七八九"


def int_to_zh(n: int) -> str:
    if n >= 10000:
        hi, lo = divmod(n, 10000)
        return int_to_zh(hi) + "萬" + (("零" if lo < 1000 else "") + int_to_zh(lo) if lo else "")
    if n == 0:
        return "零"
    out, zero, digits = "", False, str(n)
    for i, ch in enumerate(digits):
        d, u = int(ch), len(digits) - 1 - i
        if d == 0:
            zero = True
            continue
        if zero and out:
            out += "零"
        zero = False
        out += _ZH_DIGIT[d] + ["", "十", "百", "千"][u]
    return out[1:] if out.startswith("一十") else out


def num_to_zh(text: str) -> str:
    """阿拉伯數字轉中文讀法（整數用位數讀法，小數點後逐字），並去掉數字前後的空白。"""
    def rep(m):
        whole, _, frac = m.group(1).partition(".")
        return int_to_zh(int(whole)) + ("點" + "".join(_ZH_DIGIT[int(c)] for c in frac) if frac else "")
    return re.sub(r"\s*(\d+(?:\.\d+)?)\s*", rep, text)


def load_listening(path) -> None:
    global LISTEN, RUNS, WARMUP
    items = json.loads(Path(path).read_text(encoding="utf-8"))
    SENTENCES.clear()
    for it in items:
        LISTEN_RAW[it["id"]] = it["text"]
        SENTENCES[it["id"]] = num_to_zh(it["text"])
    LISTEN, RUNS, WARMUP = True, int(os.environ.get("LIVE_TTS_RUNS", "1")), 0

# 兩組參考音（都存「音檔＋同名逐字稿 .txt」，VSF exp/research-archive 801c0b3 07-配音參考音來源.md）。
REF_SETS = {
    # JVNV 日文女聲 voice-female-f1.wav 裁 0.0–9.6 秒（前兩句）。逐字稿來源：faster-whisper small ASR
    # （artifacts/stt/voice-female-f1.json）＋ tools/fixtures/cosyvoice/reference-female-text.txt 人工修正。
    "f1": {"text": "最近、自分の人生に充実感を感じているんだ。友達、家族、そして仕事もうまくいっている。",
           "lang": "ja", "clip_end_s": 9.6, "clip_name": "voice-female-f1-0-9.6s.wav"},
    # Qwen3-TTS 官方中文（大陸口音）女聲示範音，4.20 秒 16 kHz，不裁切。
    # URL：https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen3-TTS-Repo/clone_1.wav
    # 逐字稿來源：https://github.com/QwenLM/Qwen3-TTS/blob/main/examples/test_model_12hz_base.py ref_text_batch[1]
    "qwen-zh": {"text": "甚至出现交易几乎停滞的情况。", "lang": "zh", "clip_end_s": None,
                "clip_name": "qwen3-tts-clone_1.wav"},
    # 「和變聲同一人」：VoxCPM2（Qwen 中文示範音克隆）合成中文句 → RVC Sage_CN_HeroicFemale（FCPE、pitch 0、index 0.75）。
    # 逐字稿＝合成時的輸入文字，再以 faster-whisper 轉寫比對（見研究文件）。由 make_zh_source.py＋tools/rvc-fcpe-gpu-infer.py 產生。
    "rvc-sage": {"text": "歡迎來到我的直播間，今天天氣有點冷，大家記得多穿一點衣服，我們先來看看留言吧。", "lang": "zh",
                 "clip_end_s": None, "clip_name": "rvc-sage-zh.wav"},
}
REF_NAME = "f1"
REF_TEXT = REF_SETS["f1"]["text"]
REF_LANG = REF_SETS["f1"]["lang"]
REF_CLIP_END_S = REF_SETS["f1"]["clip_end_s"]


def select_ref(name: str) -> None:
    global REF_NAME, REF_TEXT, REF_LANG, REF_CLIP_END_S
    cfg = REF_SETS[name]
    REF_NAME, REF_TEXT, REF_LANG, REF_CLIP_END_S = name, cfg["text"], cfg["lang"], cfg["clip_end_s"]


def prepare_ref(src: Path, out_dir: Path) -> Path:
    """依目前參考音組，在 out_dir/../ref/ 建立共用參考音與同名逐字稿。"""
    return make_ref_clip(Path(src), Path(out_dir).parent / "ref" / REF_SETS[REF_NAME]["clip_name"], REF_CLIP_END_S)


WARMUP = 1
RUNS = 3


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest().upper()


def make_ref_clip(src: Path, dst: Path, end_s: float | None = None) -> Path:
    """用標準庫 wave 裁出參考音前段，四個後端共用同一個檔。"""
    dst = Path(dst)
    # 逐字稿與參考音同名存放（VSF exp/research-archive 801c0b3 07-配音參考音來源.md 建議）。
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.with_suffix(".txt").write_text(REF_TEXT + "\n", encoding="utf-8")
    if dst.exists():
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(src), "rb") as r:
        params = r.getparams()
        frames = r.readframes(int(end_s * r.getframerate()) if end_s else r.getnframes())
    with wave.open(str(dst), "wb") as w:
        w.setparams(params)
        w.writeframes(frames)
    return dst


def write_wav(path: Path, audio: np.ndarray, sr: int) -> None:
    audio = np.clip(np.asarray(audio, dtype=np.float32).reshape(-1), -1.0, 1.0)
    pcm = (audio * 32767.0).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes(pcm.tobytes())


def nvidia_smi_snapshot() -> str:
    try:
        return subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=20).stdout
    except Exception as exc:  # noqa: BLE001
        return f"nvidia-smi 失敗：{exc}"


class GpuSampler:
    """每 0.2 秒取樣整張卡的已用 VRAM 與使用率（含其他行程，所以另報 torch 峰值）。"""

    def __init__(self, interval: float = 0.2):
        self.interval = interval
        self.samples: list[tuple[float, float]] = []
        self._stop = threading.Event()
        self._t: threading.Thread | None = None

    def _loop(self):
        while not self._stop.is_set():
            try:
                out = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=5,
                ).stdout.strip().splitlines()[0]
                mem, util = (float(x) for x in out.split(","))
                self.samples.append((mem, util))
            except Exception:  # noqa: BLE001
                pass
            self._stop.wait(self.interval)

    def __enter__(self):
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._t:
            self._t.join(timeout=10)

    def summary(self):
        if not self.samples:
            return None
        mems = [m for m, _ in self.samples]
        utils = [u for _, u in self.samples]
        return {"gpu_mem_used_mib_max": max(mems), "gpu_mem_used_mib_min": min(mems),
                "gpu_util_pct_mean": round(statistics.mean(utils), 1), "n": len(self.samples)}


def _torch():
    try:
        import torch  # noqa: PLC0415
        return torch if torch.cuda.is_available() else None
    except Exception:  # noqa: BLE001
        return None


def _to_np(chunk) -> np.ndarray:
    if hasattr(chunk, "detach"):
        chunk = chunk.detach().float().cpu().numpy()
    return np.asarray(chunk, dtype=np.float32).reshape(-1)


def measure_once(synth: Callable[[str], Iterable], text: str, sr: int):
    torch = _torch()
    if torch:
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    first = None
    chunks = []
    for c in synth(text):
        a = _to_np(c)
        if a.size == 0:
            continue
        if first is None:
            first = time.perf_counter() - t0
        chunks.append(a)
    total = time.perf_counter() - t0
    audio = np.concatenate(chunks) if chunks else np.zeros(0, np.float32)
    dur = audio.size / sr if sr else 0.0
    return {
        "first_chunk_s": first,
        "total_s": total,
        "audio_s": dur,
        "rtf": (total / dur) if dur else None,
        "n_chunks": len(chunks),
        "streamed": bool(len(chunks) > 1 and first is not None and first < 0.8 * total),
        "finite": bool(np.isfinite(audio).all()),
        "rms": float(np.sqrt(np.mean(audio ** 2))) if audio.size else 0.0,
    }, audio


def run_bench(backend: str, synth: Callable[[str], Iterable], sr: int, out_dir: Path,
              meta: dict, ref_clip: Path, load_seconds: float | None = None) -> dict:
    backend = f"{backend}@{REF_NAME}"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    torch = _torch()
    result = {
        "backend": backend,
        "started_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "host": platform.node(),
        "python": platform.python_version(),
        "meta": meta,
        "reference": {"set": REF_NAME, "path": str(ref_clip), "sha256": sha256(ref_clip), "text": REF_TEXT,
                       "lang": REF_LANG, "clip_end_s": REF_CLIP_END_S},
        "load_seconds": load_seconds,
        "nvidia_smi_before": nvidia_smi_snapshot(),
        "sentences": {},
    }
    if torch:
        result["torch"] = {"version": torch.__version__, "device": torch.cuda.get_device_name(0)}
    if LISTEN:
        result["global_warmup"] = {"text": WARMUP_TEXT, "metrics": measure_once(synth, WARMUP_TEXT, sr)[0]}
    for key, text in SENTENCES.items():
        if torch:
            torch.cuda.reset_peak_memory_stats()
        entry = {"text": text, "chars": len(text), "warmup": [], "runs": []}
        if LISTEN:
            entry["raw_text"] = LISTEN_RAW.get(key)
        with GpuSampler() as sampler:
            for _ in range(WARMUP):
                m, _a = measure_once(synth, text, sr)
                entry["warmup"].append(m)
            for i in range(RUNS):
                m, audio = measure_once(synth, text, sr)
                entry["runs"].append(m)
                if i == 0:
                    wav = out_dir / f"{backend}-{key}.wav"
                    write_wav(wav, audio, sr)
                    entry["sample_wav"] = {"path": str(wav), "sha256": sha256(wav)}
        entry["gpu_sampler"] = sampler.summary()
        if torch:
            entry["torch_max_allocated_mib"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
            entry["torch_max_reserved_mib"] = round(torch.cuda.max_memory_reserved() / 2**20, 1)
        firsts = [r["first_chunk_s"] for r in entry["runs"] if r["first_chunk_s"] is not None]
        rtfs = [r["rtf"] for r in entry["runs"] if r["rtf"]]
        entry["summary"] = {
            "first_chunk_ms_p50": round(statistics.median(firsts) * 1000, 1) if firsts else None,
            "first_chunk_ms_max": round(max(firsts) * 1000, 1) if firsts else None,
            "rtf_p50": round(statistics.median(rtfs), 3) if rtfs else None,
            "audio_s_p50": round(statistics.median([r["audio_s"] for r in entry["runs"]]), 2),
            "streamed_all": all(r["streamed"] for r in entry["runs"]),
        }
        result["sentences"][key] = entry
        print(key, json.dumps(entry["summary"], ensure_ascii=False), flush=True)
    result["nvidia_smi_after"] = nvidia_smi_snapshot()
    result["finished_at"] = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
    js = out_dir / f"{backend}-result.json"
    js.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RESULT_JSON", js, flush=True)
    return result


if os.environ.get("LIVE_TTS_SENTENCES"):
    load_listening(os.environ["LIVE_TTS_SENTENCES"])
