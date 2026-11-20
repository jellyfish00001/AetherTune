"""VoxCPM2 generate_streaming 量測（預建 prompt cache，不算進首包）。"""
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
    ap.add_argument("--mode", choices=["ultimate", "reference"], default="ultimate",
                    help="ultimate=參考音+精確逐字稿續寫＋reference；reference=只用 reference 音色")
    ap.add_argument("--timesteps", type=int, default=10)
    ap.add_argument("--optimize", action="store_true", help="torch.compile（Windows 需 triton，預設關）")
    a = ap.parse_args()
    out = Path(a.out_dir)
    ref = str(common.make_ref_clip(Path(a.ref_src), out.parent / "ref" / "voice-female-f1-0-9.6s.wav"))
    from voxcpm import VoxCPM

    t = time.perf_counter()
    vc = VoxCPM(voxcpm_model_path=a.model_dir, zipenhancer_model_path=None, enable_denoiser=False,
                optimize=a.optimize)
    if a.mode == "ultimate":
        cache = vc.tts_model.build_prompt_cache(prompt_text=common.REF_TEXT, prompt_wav_path=ref,
                                                reference_wav_path=ref)
    else:
        cache = vc.tts_model.build_prompt_cache(prompt_text=None, prompt_wav_path=None, reference_wav_path=ref)
    load = time.perf_counter() - t

    def synth(text):
        gen = vc.tts_model._generate_with_prompt_cache(
            target_text=text, prompt_cache=cache, min_len=2, max_len=4096,
            inference_timesteps=a.timesteps, cfg_value=2.0, retry_badcase=False,
            retry_badcase_max_times=0, retry_badcase_ratio_threshold=6.0, streaming=True)
        try:
            for wav, _, _ in gen:
                yield wav.squeeze(0)
        finally:
            gen.close()

    sr = getattr(vc.tts_model, "sample_rate", None) or vc.tts_model.audio_vae.sample_rate
    common.run_bench(f"voxcpm2-{a.mode}-t{a.timesteps}", synth, sr, out,
                     {"package": "voxcpm==2.0.3", "model": "openbmb/VoxCPM2", "mode": a.mode,
                      "inference_timesteps": a.timesteps, "cfg_value": 2.0, "optimize": a.optimize,
                      "retry_badcase": False}, Path(ref), load)


if __name__ == "__main__":
    main()