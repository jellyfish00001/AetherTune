"""CosyVoice2-0.5B stream=True 基準（在 PC1 WSL 既有 venv 內執行，唯讀使用）。

一次載入模型，依序跑多組（參考音組 × 是否用預建聲線 ID），避免 WSL /mnt/d 重複載入權重很慢。
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--ref-src", action="append", required=True, help="格式 set=path，可重複")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--fp16", action="store_true")
    ap.add_argument("--combos", default="qwen-zh:spk,qwen-zh:nospk,f1:spk,f1:nospk",
                    help="逗號分隔的 參考音組:spk|nospk；spk=預建聲線 ID，nospk=每次傳參考音與逐字稿")
    a = ap.parse_args()
    srcs = dict(s.split("=", 1) for s in a.ref_src)
    out = Path(a.out_dir)
    from cosyvoice.cli.cosyvoice import CosyVoice2

    t = time.perf_counter()
    cv = CosyVoice2(a.model_dir, fp16=a.fp16)
    load = time.perf_counter() - t
    for combo in a.combos.split(","):
        ref_set, mode = combo.split(":")
        common.select_ref(ref_set)
        ref = common.prepare_ref(Path(srcs[ref_set]), out)
        spk_id = f"spk-{ref_set}"
        t2 = time.perf_counter()
        if mode == "spk":
            # 參考音特徵先快取成 zero-shot 聲線 ID，直播時常駐，不算進首包。
            cv.add_zero_shot_spk(common.REF_TEXT, str(ref), spk_id)
        spk_seconds = time.perf_counter() - t2

        def synth(text, mode=mode, ref=ref, spk_id=spk_id):
            if mode == "nospk":
                gen = cv.inference_zero_shot(text, common.REF_TEXT, str(ref), stream=True)
            else:
                gen = cv.inference_zero_shot(text, "", "", zero_shot_spk_id=spk_id, stream=True)
            for item in gen:
                yield item["tts_speech"]

        name = "cosyvoice2" + ("-fp16" if a.fp16 else "") + ("-nospkid" if mode == "nospk" else "")
        common.run_bench(name, synth, cv.sample_rate, out,
                         {"model": "CosyVoice2-0.5B", "stream": True, "fp16": a.fp16, "spk_id": mode == "spk",
                          "spk_cache_seconds": round(spk_seconds, 3),
                          "token_hop_len": getattr(cv.model, "token_hop_len", None)}, ref, load)


if __name__ == "__main__":
    main()