"""產生「和變聲同一人」的中文參考音來源句：用 VoxCPM2＋Qwen 官方中文女聲示範音合成一段 7–10 秒中文，
之後交給 RVC（Sage 等女聲模型）轉成變聲目標音色。輸出 wav 與同名逐字稿。"""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

TEXT = "歡迎來到我的直播間，今天天氣有點冷，大家記得多穿一點衣服，我們先來看看留言吧。"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    common.select_ref("qwen-zh")
    from voxcpm import VoxCPM

    vc = VoxCPM(voxcpm_model_path=a.model_dir, zipenhancer_model_path=None, enable_denoiser=False, optimize=False)
    wav = vc.generate(text=TEXT, prompt_wav_path=a.ref, prompt_text=common.REF_TEXT, reference_wav_path=a.ref)
    sr = getattr(vc.tts_model, "sample_rate", None) or vc.tts_model.audio_vae.sample_rate
    out = Path(a.out)
    common.write_wav(out, np.asarray(wav), sr)
    out.with_suffix(".txt").write_text(TEXT + "\n", encoding="utf-8")
    print("OUT", out, len(wav) / sr, "s")


if __name__ == "__main__":
    main()