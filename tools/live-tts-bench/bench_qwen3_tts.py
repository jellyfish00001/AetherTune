"""Qwen3-TTS Base 語音複製量測（qwen-tts 開源套件無串流生成介面）。"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def base_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--ref-src", required=True)
    ap.add_argument("--out-dir", required=True)
    return ap

def main():
    ap = base_args()
    ap.add_argument("--xvec-only", action="store_true")
    a = ap.parse_args()
    out = Path(a.out_dir)
    ref = str(common.make_ref_clip(Path(a.ref_src), out.parent / "ref" / "voice-female-f1-0-9.6s.wav"))
    import torch
    from qwen_tts import Qwen3TTSModel

    t = time.perf_counter()
    model = Qwen3TTSModel.from_pretrained(a.model_dir, device_map="cuda:0", dtype=torch.bfloat16,
                                          attn_implementation="sdpa")
    prompt = model.create_voice_clone_prompt(ref_audio=ref, ref_text=common.REF_TEXT,
                                             x_vector_only_mode=a.xvec_only)
    load = time.perf_counter() - t
    sr_box = {}

    def synth(text):
        wavs, sr = model.generate_voice_clone(text=text, language="Chinese", voice_clone_prompt=prompt)
        sr_box["sr"] = sr
        yield wavs[0]

    # 取樣率先跑一次取得
    list(synth("你好"))
    name = "qwen3-tts-" + Path(a.model_dir).name.replace("qwen3-tts-", "") + ("-xvec" if a.xvec_only else "")
    common.run_bench(name, synth, sr_box["sr"], out,
                     {"package": "qwen-tts==0.1.1", "model": Path(a.model_dir).name, "dtype": "bfloat16",
                      "attn": "sdpa", "x_vector_only": a.xvec_only, "streaming": False,
                      "note": "qwen-tts 0.1.1 的 non_streaming_mode 只模擬串流文字輸入，不是串流生成；首包=整句"},
                     Path(ref), load)


if __name__ == "__main__":
    main()