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
    ap.add_argument("--ref-set", choices=sorted(common.REF_SETS), default="f1")
    return ap

def main():
    ap = base_args()
    ap.add_argument("--bert", action="store_true", help="use_bert=True（README 建議中文開）")
    ap.add_argument("--sdp", choices=["efficient", "math", "auto"], default="efficient",
                    help="gsv-tts-lite 0.4.7 自動選 CUDNN_ATTENTION，在 PC1 5060 Ti/Windows 帶 mask 時報 No available kernel，預設改 EFFICIENT")
    a = ap.parse_args()
    common.select_ref(a.ref_set)
    out = Path(a.out_dir)
    ref = str(common.prepare_ref(Path(a.ref_src), out))
    from gsv_tts import TTS

    if a.sdp != "auto":
        # 只在本行程覆寫注意力後端，不改套件檔。
        from torch.nn.attention import SDPBackend
        import gsv_tts.GPT_SoVITS.GPT.t2s_model as t2s
        t2s.SDPBACKEND = SDPBackend.EFFICIENT_ATTENTION if a.sdp == "efficient" else SDPBackend.MATH
        try:
            import gsv_tts.GPT_SoVITS.GPT.t2s_model_flash_attn as t2sf
            t2sf.SDPBACKEND = t2s.SDPBACKEND
        except Exception:  # noqa: BLE001
            pass

    t = time.perf_counter()
    tts = TTS(models_dir=a.model_dir, use_bert=a.bert)
    tts.load_gpt_model()
    tts.load_sovits_model()
    tts.init_language_module("zh")
    tts.init_language_module("ja")
    tts.cache_spk_audio(ref)
    tts.cache_prompt_audio(prompt_audio_paths=ref, prompt_audio_texts=common.REF_TEXT, prompt_language=common.REF_LANG)
    load = time.perf_counter() - t

    def synth(text):
        for clip in tts.infer_stream(spk_audio_path=ref, prompt_audio_path=ref, prompt_audio_text=common.REF_TEXT,
                                     text=text, text_language="zh", prompt_language=common.REF_LANG, debug=False):
            yield clip.audio_data

    common.run_bench("gsv-tts-lite" + ("-bert" if a.bert else ""), synth, tts.samplerate, out,
                     {"package": "gsv-tts-lite==0.4.7", "model": "s1v3.ckpt + s2Gv2ProPlus.pth（內建底模）",
                      "stream_mode": "token", "stream_chunk": 25, "overlap_len": 5, "use_bert": a.bert,
                      "flash_attn": False, "sdp_backend": a.sdp}, Path(ref), load)


if __name__ == "__main__":
    main()