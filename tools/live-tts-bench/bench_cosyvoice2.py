"""CosyVoice2-0.5B stream=True 基準（在 PC1 WSL 既有 venv 內執行，唯讀使用）。"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--ref-src", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--fp16", action="store_true")
    ap.add_argument("--no-spk-id", action="store_true", help="不用預建聲線 ID，每次都傳參考音路徑與逐字稿")
    a = ap.parse_args()
    out = Path(a.out_dir)
    ref = common.make_ref_clip(Path(a.ref_src), out.parent / "ref" / "voice-female-f1-0-9.6s.wav")
    from cosyvoice.cli.cosyvoice import CosyVoice2

    t = time.perf_counter()
    cv = CosyVoice2(a.model_dir, fp16=a.fp16)
    # 參考音特徵先快取成 zero-shot speaker，直播時常駐，不算進首包。
    cv.add_zero_shot_spk(common.REF_TEXT, str(ref), "f1")
    load = time.perf_counter() - t

    def synth(text):
        if a.no_spk_id:
            gen = cv.inference_zero_shot(text, common.REF_TEXT, str(ref), stream=True)
        else:
            gen = cv.inference_zero_shot(text, "", "", zero_shot_spk_id="f1", stream=True)
        for item in gen:
            yield item["tts_speech"]

    name = "cosyvoice2" + ("-fp16" if a.fp16 else "") + ("-nospkid" if a.no_spk_id else "")
    common.run_bench(name, synth, cv.sample_rate, out,
                     {"model": "CosyVoice2-0.5B", "stream": True, "fp16": a.fp16, "spk_id": not a.no_spk_id,
                      "token_hop_len": getattr(cv.model, "token_hop_len", None)}, ref, load)


if __name__ == "__main__":
    main()
