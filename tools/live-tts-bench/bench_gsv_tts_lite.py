"""GSV-TTS-Lite（GPT-SoVITS V2ProPlus 加速後端）infer_stream 量測。"""
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
    ap.add_argument("--bert", action="store_true", help="use_bert=True（README 建議中文開）")
    a = ap.parse_args()
    out = Path(a.out_dir)
    ref = str(common.make_ref_clip(Path(a.ref_src), out.parent / "ref" / "voice-female-f1-0-9.6s.wav"))
    from gsv_tts import TTS

    t = time.perf_counter()
    tts = TTS(models_dir=a.model_dir, use_bert=a.bert)
    tts.load_gpt_model()
    tts.load_sovits_model()
    tts.init_language_module("zh")
    tts.init_language_module("ja")
    tts.cache_spk_audio(ref)
    tts.cache_prompt_audio(prompt_audio_paths=ref, prompt_audio_texts=common.REF_TEXT, prompt_language="ja")
    load = time.perf_counter() - t

    def synth(text):
        for clip in tts.infer_stream(spk_audio_path=ref, prompt_audio_path=ref, prompt_audio_text=common.REF_TEXT,
                                     text=text, text_language="zh", prompt_language="ja", debug=False):
            yield clip.audio_data

    common.run_bench("gsv-tts-lite" + ("-bert" if a.bert else ""), synth, tts.samplerate, out,
                     {"package": "gsv-tts-lite==0.4.7", "model": "s1v3.ckpt + s2Gv2ProPlus.pth（內建底模）",
                      "stream_mode": "token", "stream_chunk": 25, "overlap_len": 5, "use_bert": a.bert,
                      "flash_attn": False}, Path(ref), load)


if __name__ == "__main__":
    main()