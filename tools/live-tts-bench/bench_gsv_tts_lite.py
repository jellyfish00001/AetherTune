"""GSV-TTS-Lite（GPT-SoVITS V2ProPlus 加速後端）infer_stream 量測。"""
import argparse
import json
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
    ap.add_argument("--no-boost", action="store_true", help="boost_first_chunk=False（官方說 True 會降首包但短句可能有雜音）")
    ap.add_argument("--stream-chunk", type=int, default=25)
    ap.add_argument("--overlap", type=int, default=5)
    ap.add_argument("--flash-attn", action="store_true", help="use_flash_attn=True（需實驗 venv 內裝 flash-attn Windows 輪檔）")
    ap.add_argument("--no-en-warmup", action="store_true",
                    help="不做 common.GSV_WARMUP_TEXTS 常駐暖機（對照用：第一句含英文時首包約 5.6 s）")
    ap.add_argument("--cut-minlen", type=int, default=10, help="切句最短長度；預設 10 會把短子句併到下一句")
    ap.add_argument("--zh-fix", action="store_true",
                    help="純中日韓文字時略過 LangSegment 語言偵測、整段當中文；修 0.4.7 遇到「囉」等字整段被丟掉的尾句截斷")
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

    if a.zh_fix:
        import re
        import gsv_tts.TextProcessor as tp
        _orig = tp.LangSegment.getTexts

        def _zh_only(text, *args, **kw):
            if re.search(r"[A-Za-z]", text):
                return _orig(text, *args, **kw)
            return [{"lang": "zh", "text": text}]
        tp.LangSegment.getTexts = staticmethod(_zh_only)

    t = time.perf_counter()
    tts = TTS(models_dir=a.model_dir, use_bert=a.bert, use_flash_attn=a.flash_attn,
              sovits_cache=[a.stream_chunk * 2, a.stream_chunk * 2 + a.overlap])
    tts.load_gpt_model()
    tts.load_sovits_model()
    tts.init_language_module("zh")
    tts.init_language_module("ja")
    tts.cache_spk_audio(ref)
    tts.cache_prompt_audio(prompt_audio_paths=ref, prompt_audio_texts=common.REF_TEXT, prompt_language=common.REF_LANG)
    load = time.perf_counter() - t

    def synth(text):
        for clip in tts.infer_stream(spk_audio_path=ref, prompt_audio_path=ref, prompt_audio_text=common.REF_TEXT,
                                     text=text, text_language="zh", prompt_language=common.REF_LANG, debug=False,
                                     boost_first_chunk=not a.no_boost, stream_chunk=a.stream_chunk,
                                     overlap_len=a.overlap, cut_minlen=a.cut_minlen):
            yield clip.audio_data

    warm = {}
    if not a.no_en_warmup:
        for wt in common.GSV_WARMUP_TEXTS:
            t1 = time.perf_counter()
            for _ in synth(wt):
                pass
            warm[wt] = round(time.perf_counter() - t1, 3)
        print("GSV_WARMUP", json.dumps(warm, ensure_ascii=False), flush=True)

    name = "gsv-tts-lite" + ("-bert" if a.bert else "") + ("-noboost" if a.no_boost else "")
    if a.flash_attn:
        name += "-fa"
    if a.sdp != "efficient":
        name += f"-sdp{a.sdp}"
    if a.zh_fix:
        name += "-zhfix"
    if a.no_en_warmup:
        name += "-noenwarm"
    if a.cut_minlen != 10:
        name += f"-cut{a.cut_minlen}"
    if (a.stream_chunk, a.overlap) != (25, 5):
        name += f"-c{a.stream_chunk}o{a.overlap}"
    common.run_bench(name, synth, tts.samplerate, out,
                     {"package": "gsv-tts-lite==0.4.7", "model": "s1v3.ckpt + s2Gv2ProPlus.pth（內建底模）",
                      "stream_mode": "token", "stream_chunk": a.stream_chunk, "overlap_len": a.overlap,
                      "boost_first_chunk": not a.no_boost, "use_bert": a.bert,
                      "flash_attn": bool(getattr(tts.tts_config, "use_flash_attn", False)), "sdp_backend": a.sdp, "cut_minlen": a.cut_minlen, "zh_fix": a.zh_fix,
                      "en_warmup_s": warm or None}, Path(ref), load)


if __name__ == "__main__":
    main()