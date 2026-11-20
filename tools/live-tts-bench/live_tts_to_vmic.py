"""最小原型：打字 → GSV-TTS-Lite 串流合成 → 播到虛擬麥克風的輸入端（例如 VB-CABLE「CABLE Input」或 Voicemod）。

只在 exp/live-tts-bench 實驗用，不接 AetherTune 主程式。
用法（PC1，gsv-tts-lite venv）：
  python live_tts_to_vmic.py --list-devices
  python live_tts_to_vmic.py --device "CABLE Input" --ref <參考音.wav>   # 逐字稿讀同名 .txt
然後每輸入一行文字按 Enter 就念出來；空行或 Ctrl+Z 結束。每句記錄「送出 → 第一塊音訊寫進裝置」的時間。
"""

import argparse
import json
import queue
import sys
import threading
import time
from pathlib import Path

import numpy as np


def pick_device(sd, name):
    if name is None:
        return None
    for i, d in enumerate(sd.query_devices()):
        if name.lower() in d["name"].lower() and d["max_output_channels"] > 0:
            return i
    raise SystemExit(f"找不到輸出裝置：{name}（先用 --list-devices 看名稱）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-devices", action="store_true")
    ap.add_argument("--device", help="輸出裝置名稱片段，例如 CABLE Input；不填就用預設喇叭")
    ap.add_argument("--ref", help="參考音 wav（同名 .txt 為逐字稿）")
    ap.add_argument("--ref-lang", default="zh")
    ap.add_argument("--model-dir", default=r"D:\AetherTune-exp\tts-models\gsv-tts-lite")
    ap.add_argument("--no-boost", action="store_true")
    ap.add_argument("--loopback", help="同時錄虛擬線的錄音端（例如 CABLE Output），量「送出 → 線上真的出現聲音」")
    ap.add_argument("--threshold", type=float, default=0.01)
    ap.add_argument("--text-file", help="UTF-8 文字檔，一行一句（自動化量測用；不填就讀 stdin）")
    ap.add_argument("--log", default=r"D:\AetherTune-exp\artifacts\live-tts-bench\vmic\latency-log.jsonl")
    a = ap.parse_args()
    import sounddevice as sd

    if a.list_devices:
        for i, d in enumerate(sd.query_devices()):
            if d["max_output_channels"] > 0:
                print(i, d["name"], d["hostapi"], int(d["default_samplerate"]))
        return
    if not a.ref:
        raise SystemExit("需要 --ref")
    ref = str(Path(a.ref).resolve())
    ref_text = Path(ref).with_suffix(".txt").read_text(encoding="utf-8").strip()

    from torch.nn.attention import SDPBackend
    import gsv_tts.GPT_SoVITS.GPT.t2s_model as t2s
    t2s.SDPBACKEND = SDPBackend.EFFICIENT_ATTENTION  # 5060 Ti/Windows 的 CUDNN 注意力會報錯
    import re
    import gsv_tts.TextProcessor as tp
    _orig = tp.LangSegment.getTexts

    def _zh_only(text, *args, **kw):  # 同 bench --zh-fix：避免「囉」等字讓整段被語言偵測丟掉
        return _orig(text, *args, **kw) if re.search(r"[A-Za-z]", text) else [{"lang": "zh", "text": text}]
    tp.LangSegment.getTexts = staticmethod(_zh_only)
    from gsv_tts import TTS

    tts = TTS(models_dir=a.model_dir)
    tts.load_gpt_model()
    tts.load_sovits_model()
    tts.init_language_module("zh")
    tts.cache_spk_audio(ref)
    tts.cache_prompt_audio(prompt_audio_paths=ref, prompt_audio_texts=ref_text, prompt_language=a.ref_lang)
    sr = tts.samplerate
    dev = pick_device(sd, a.device)
    q: "queue.Queue[np.ndarray | None]" = queue.Queue()
    first_written = {}
    out_latency = {}
    heard = {}
    armed = {"n": None}
    in_stream = None
    if a.loopback:
        ldev = None
        for i, d in enumerate(sd.query_devices()):
            if a.loopback.lower() in d["name"].lower() and d["max_input_channels"] > 0:
                ldev = i
                break
        if ldev is None:
            raise SystemExit(f"找不到錄音裝置：{a.loopback}")

        def on_in(indata, frames, tinfo, status):
            now = time.perf_counter()
            n_ = armed["n"]
            if n_ is None or n_ in heard:
                return
            amp = np.abs(indata[:, 0])
            idx = np.nonzero(amp > a.threshold)[0]
            if len(idx):
                heard[n_] = now - (frames - int(idx[0])) / in_sr
        in_sr = int(sd.query_devices(ldev)["default_samplerate"])
        in_stream = sd.InputStream(samplerate=in_sr, channels=1, dtype="float32", device=ldev,
                                   latency="low", blocksize=256, callback=on_in)
        in_stream.start()

    def player():
        with sd.OutputStream(samplerate=sr, channels=1, dtype="float32", device=dev, latency="low") as st:
            out_latency["s"] = st.latency
            while True:
                item = q.get()
                if item is None:
                    break
                tag, buf = item
                if tag not in first_written:
                    first_written[tag] = time.perf_counter()
                st.write(buf.reshape(-1, 1))

    th = threading.Thread(target=player, daemon=True)
    th.start()
    log = Path(a.log)
    log.parent.mkdir(parents=True, exist_ok=True)
    # 暖機一次，避免第一句吃到 CUDA graph 建立時間
    for _ in tts.infer_stream(spk_audio_path=ref, prompt_audio_path=ref, prompt_audio_text=ref_text,
                              text="你好。", text_language="zh", prompt_language=a.ref_lang, debug=False):
        pass
    print("準備好了，輸入文字後按 Enter：", flush=True)
    n = 0
    lines = (Path(a.text_file).read_text(encoding="utf-8").splitlines() if a.text_file else sys.stdin)
    for line in lines:
        text = line.strip()
        if not text:
            break
        n += 1
        t0 = time.perf_counter()
        armed["n"] = n
        first_chunk = None
        audio_s = 0.0
        for clip in tts.infer_stream(spk_audio_path=ref, prompt_audio_path=ref, prompt_audio_text=ref_text,
                                     text=text, text_language="zh", prompt_language=a.ref_lang, debug=False,
                                     boost_first_chunk=not a.no_boost):
            buf = np.asarray(clip.audio_data, dtype=np.float32)
            if hasattr(clip.audio_data, "detach"):
                buf = clip.audio_data.detach().float().cpu().numpy()
            if first_chunk is None:
                first_chunk = time.perf_counter() - t0
            q.put((n, buf))
            audio_s += len(buf) / sr
        gen_done = time.perf_counter() - t0
        while n not in first_written:
            time.sleep(0.005)
        if in_stream is not None:
            t_wait = time.perf_counter()
            while n not in heard and time.perf_counter() - t_wait < 3:
                time.sleep(0.005)
        # 等這句播完再送下一句，避免下一句的量測被前一句還在播的音訊干擾
        while not q.empty():
            time.sleep(0.01)
        time.sleep(max(0.0, first_written[n] + audio_s + 0.4 - time.perf_counter()))
        rec = {"n": n, "text": text, "device": a.device, "first_chunk_ms": round(first_chunk * 1000, 1),
               "first_write_ms": round((first_written[n] - t0) * 1000, 1), "gen_total_ms": round(gen_done * 1000, 1),
               "out_stream_latency_ms": round(out_latency.get("s", 0) * 1000, 1),
               "heard_on_line_ms": round((heard[n] - t0) * 1000, 1) if n in heard else None,
               "ref": Path(ref).name}
        print(json.dumps(rec, ensure_ascii=False), flush=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    q.put(None)
    th.join()


if __name__ == "__main__":
    main()