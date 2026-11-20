"""VoxCPM2 與 VSF 對齊量測（對照 VisualSoundForge exp/tts-install 309200a 的 vsf_run_voxcpm2.py、vsfmeasure.py，只讀）。

對齊項目：VoxCPM.from_pretrained(load_denoiser=False)、model.generate(text, prompt_wav_path=ref, prompt_text=rt,
reference_wav_path=ref, cfg_value=2.0, inference_timesteps=N)，其他參數用套件預設（含 retry_badcase=True），
參考音 D:\\VSF\\tts\\refs\\clone_1.wav / clone_2.wav（只讀），句子 zh1/zh2/en1/en2，先暖機 zh1 一次不列入。
RTF = 生成秒數 ÷ 音檔秒數；每句前 cuda.synchronize + reset_peak_memory_stats，量完再 synchronize。
差異：明確傳 optimize=False（VSF 的 venv 沒有 triton，torch.compile 自動停用；我們的 venv 有 triton，不關會編譯）。
另外加量：每句 3 次（VSF 1 次）、串流 generate_streaming 的首包（同參數）。
"""
import argparse
import json
import statistics
import subprocess
import time
from pathlib import Path

REFS = {
    "ZH": (r"D:\VSF\tts\refs\clone_1.wav", "甚至出现交易几乎停滞的情况。"),
    "EN": (r"D:\VSF\tts\refs\clone_2.wav",
           "Okay. Yeah. I resent you. I love you. I respect you. But you know what? You blew it! And thanks to you."),
}
LISTEN = [
    ("zh1", "ZH", "雨停了，我們回家吧。路上小心，別再淋濕了。"),
    ("zh2", "ZH", "你知道嗎？那天晚上我其實一直在等你，可是你始終沒有出現。"),
    ("en1", "EN", "The rain has finally stopped. Let's head home before it gets dark."),
    ("en2", "EN", "Do you know what? I waited for you all night, but you never showed up."),
]


def nvsmi():
    try:
        return subprocess.run(["nvidia-smi", "--query-gpu=memory.used,utilization.gpu", "--format=csv,noheader"],
                              capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"ERR {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--timesteps", default="10,6")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--modes", default="hifi", help="逗號分隔：hifi（三個都給）、prompt（只給 prompt_wav+prompt_text）、ref（只給 reference_wav）")
    ap.add_argument("--no-stream", action="store_true")
    a = ap.parse_args()
    import numpy as np
    import soundfile as sf
    import torch
    from voxcpm import VoxCPM

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    res = {"vsf_ref_commit": "VisualSoundForge exp/tts-install 309200a", "nvidia_smi_before": nvsmi(),
           "started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "torch": torch.__version__, "runs": []}
    t0 = time.time()
    model = VoxCPM.from_pretrained(a.model_dir, load_denoiser=False, optimize=False)
    res["load_s"] = round(time.time() - t0, 2)
    sr = model.tts_model.sample_rate

    def kwargs(lang, mode):
        ref, rt = REFS[lang]
        if mode == "hifi":
            return dict(prompt_wav_path=ref, prompt_text=rt, reference_wav_path=ref)
        if mode == "prompt":
            return dict(prompt_wav_path=ref, prompt_text=rt)
        return dict(reference_wav_path=ref)

    for mode in a.modes.split(","):
        for n in [int(x) for x in a.timesteps.split(",")]:
            # 暖機：同 VSF，先跑 zh1 一次不列入
            model.generate(text=LISTEN[0][2], cfg_value=2.0, inference_timesteps=n, **kwargs("ZH", mode))
            for item, lang, text in LISTEN:
                for r in range(a.runs):
                    torch.cuda.synchronize(); torch.cuda.reset_peak_memory_stats()
                    t = time.time()
                    wav = model.generate(text=text, cfg_value=2.0, inference_timesteps=n, **kwargs(lang, mode))
                    torch.cuda.synchronize()
                    g = time.time() - t
                    dur = len(wav) / sr
                    peak = torch.cuda.max_memory_allocated() / 2**30
                    p = out / f"voxcpm2-vsfalign-{mode}-t{n}-{item}-r{r + 1}.wav"
                    sf.write(p, wav, sr)
                    row = {"mode": mode, "timesteps": n, "item": item, "lang": lang, "run": r + 1, "stream": False,
                           "gen_s": round(g, 3), "audio_s": round(dur, 3), "rtf": round(g / dur, 3) if dur else None,
                           "vram_peak_alloc_gib": round(peak, 2), "file": str(p)}
                    res["runs"].append(row)
                    print(json.dumps(row, ensure_ascii=False), flush=True)
                if not a.no_stream:
                    for r in range(a.runs):
                        torch.cuda.synchronize(); torch.cuda.reset_peak_memory_stats()
                        t = time.time(); first = None; chunks = []
                        for ch in model.generate_streaming(text=text, cfg_value=2.0, inference_timesteps=n,
                                                           **kwargs(lang, mode)):
                            if first is None:
                                torch.cuda.synchronize(); first = time.time() - t
                            chunks.append(np.asarray(ch).reshape(-1))
                        torch.cuda.synchronize(); g = time.time() - t
                        dur = sum(len(c) for c in chunks) / sr
                        row = {"mode": mode, "timesteps": n, "item": item, "lang": lang, "run": r + 1, "stream": True,
                               "first_chunk_ms": round(first * 1000, 1) if first else None, "chunks": len(chunks),
                               "gen_s": round(g, 3), "audio_s": round(dur, 3), "rtf": round(g / dur, 3) if dur else None,
                               "vram_peak_alloc_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2)}
                        res["runs"].append(row)
                        print(json.dumps(row, ensure_ascii=False), flush=True)
    res["nvidia_smi_after"] = nvsmi()
    res["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    summ = {}
    for row in res["runs"]:
        k = f'{row["mode"]}-t{row["timesteps"]}-{"stream" if row["stream"] else "full"}-{row["item"]}'
        summ.setdefault(k, []).append(row)
    res["summary"] = {k: {"rtf_p50": statistics.median(x["rtf"] for x in v), "rtf_run1": v[0]["rtf"],
                          "first_chunk_ms_p50": (statistics.median(x["first_chunk_ms"] for x in v)
                                                 if v[0].get("first_chunk_ms") else None),
                          "audio_s_p50": statistics.median(x["audio_s"] for x in v),
                          "vram_peak_alloc_gib": max(x["vram_peak_alloc_gib"] for x in v)} for k, v in summ.items()}
    jp = out / f"voxcpm2-vsfalign-{a.modes.replace(',', '+')}-result.json"
    jp.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in res["summary"].items():
        print("SUMMARY", k, json.dumps(v), flush=True)
    print("RESULT_JSON", jp, flush=True)


if __name__ == "__main__":
    main()
