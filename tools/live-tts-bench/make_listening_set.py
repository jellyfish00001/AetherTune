"""把三個引擎的聽感對照 wav 做成盲測組：SenseVoice CER、Opus 64k、打亂編號、對照表、SHA256、評分表。

在實驗 venv D:\\AetherTune-exp\\tts-venvs\\asr-sensevoice（sherpa-onnx 2.0.2、opencc 1.4.2）執行，只用 CPU。
SenseVoice 權重：Hugging Face 公開 repo csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17 的 model.int8.onnx。
CER 先把參考與轉寫都用 OpenCC t2s 轉簡體、英文轉小寫、去標點與空白，所以簡繁算同字。
"""

import argparse
import csv
import hashlib
import json
import re
import secrets
import subprocess
from pathlib import Path

import numpy as np
import opencc
import sherpa_onnx
import soundfile as sf

from asr_check import cer

ENGINES = {  # 目錄名 → 顯示名（只寫進 metrics 與對照表，不寫進盲測檔名）
    "gsv-tts-lite": "GSV-TTS-Lite 不加速 + zh-fix",
    "voxcpm2": "VoxCPM2 6 步不 compile",
    "cosyvoice2": "CosyVoice2 簡體 + hop-fix + JIT + TRT + fp16",
}
CC = opencc.OpenCC("t2s")
TAG = re.compile(r"<\|[^|]*\|>")


def norm(t: str) -> str:
    return CC.convert(TAG.sub("", t)).lower()


def sha(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--sentences", required=True)
    ap.add_argument("--sensevoice-dir", required=True)
    ap.add_argument("--ffmpeg", required=True)
    ap.add_argument("--ref-wav", required=True)
    a = ap.parse_args()
    root = Path(a.root)
    items = {it["id"]: it for it in json.loads(Path(a.sentences).read_text(encoding="utf-8"))}
    sv = Path(a.sensevoice_dir)
    rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(
        model=str(sv / "model.int8.onnx"), tokens=str(sv / "tokens.txt"), language="zh", use_itn=False, num_threads=2)

    rows = []
    for eng, label in ENGINES.items():
        res = next((root / "raw" / eng).glob("*-result.json"))
        data = json.loads(res.read_text(encoding="utf-8"))
        for key, e in data["sentences"].items():
            wav = Path(e["sample_wav"]["path"])
            audio, sr = sf.read(str(wav), dtype="float32")
            audio = audio if audio.ndim == 1 else audio.mean(axis=1)
            st = rec.create_stream()
            st.accept_waveform(sr, audio)
            rec.decode_stream(st)
            hyp = st.result.text
            r = e["runs"][0]
            rows.append({
                "engine": eng, "engine_label": label, "sentence_id": key, "len": items[key]["len"],
                "source_text": items[key]["text"], "spoken_text": e["text"], "wav": wav,
                "first_chunk_ms": round(r["first_chunk_s"] * 1000, 1) if r["first_chunk_s"] else None,
                "rtf": round(r["rtf"], 3) if r["rtf"] else None, "audio_s": round(r["audio_s"], 2),
                "n_chunks": r["n_chunks"], "torch_max_allocated_mib": e.get("torch_max_allocated_mib"),
                "sensevoice_hyp": hyp, "cer": cer(norm(e["text"]), norm(hyp)),
            })
            print(eng, key, rows[-1]["first_chunk_ms"], rows[-1]["rtf"], rows[-1]["cer"], hyp, flush=True)

    with (root / "metrics.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["engine", "sentence_id", "len", "first_chunk_ms", "rtf", "audio_s", "n_chunks",
                    "torch_max_allocated_mib", "cer_sensevoice", "sensevoice_hyp", "spoken_text"])
        for r in rows:
            w.writerow([r["engine_label"], r["sentence_id"], r["len"], r["first_chunk_ms"], r["rtf"], r["audio_s"],
                        r["n_chunks"], r["torch_max_allocated_mib"], r["cer"], r["sensevoice_hyp"], r["spoken_text"]])

    blind = root / "blind-opus64"
    blind.mkdir(parents=True, exist_ok=True)
    order = list(rows)
    rng = secrets.SystemRandom()
    rng.shuffle(order)
    enc = ["-hide_banner", "-loglevel", "error", "-y", "-c:a", "libopus", "-b:a", "64k", "-vbr", "on",
           "-application", "audio", "-map_metadata", "-1"]
    for i, r in enumerate(order, 1):
        r["blind_id"] = f"{i:03d}"
        subprocess.run([a.ffmpeg, "-i", str(r["wav"]), *enc, str(blind / f"{r['blind_id']}.opus")], check=True)
    subprocess.run([a.ffmpeg, "-i", a.ref_wav, *enc, str(blind / "REF-參考音.opus")], check=True)

    with (root / "blind-key-DO-NOT-OPEN.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["blind_id", "engine", "sentence_id", "raw_wav"])
        for r in sorted(order, key=lambda x: x["blind_id"]):
            w.writerow([r["blind_id"], r["engine_label"], r["sentence_id"], r["wav"].relative_to(root).as_posix()])

    with (root / "score-sheet.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["編號", "句子（原文）", "自然度 1–5", "像不像參考音同一人（像／有點像／不像）", "錯字或怪音（寫出位置）", "備註"])
        for r in sorted(order, key=lambda x: x["blind_id"]):
            w.writerow([r["blind_id"], r["source_text"], "", "", "", ""])

    files = sorted(p for p in root.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt")
    (root / "SHA256SUMS.txt").write_text(
        "".join(f"{sha(p)}  {p.relative_to(root).as_posix()}\n" for p in files), encoding="utf-8")
    print("DONE", len(order), "samples", flush=True)


if __name__ == "__main__":
    main()