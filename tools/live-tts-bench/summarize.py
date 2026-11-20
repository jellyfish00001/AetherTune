r"""把 artifacts/live-tts-bench 下所有 *-result.json 彙整成 Markdown 表。

用法：python summarize.py [D:\AetherTune-exp\artifacts\live-tts-bench]
"""

import json
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else r"D:\AetherTune-exp\artifacts\live-tts-bench")
print("| 後端@參考音 | 句 | 首包 p50 ms | 首包 max ms | RTF p50 | 音長 s | torch VRAM 峰值 MiB | 整卡已用 max MiB | 真串流 | 量測時間 |")
print("|---|---|---:|---:|---:|---:|---:|---:|---|---|")
for js in sorted(root.glob("*/*-result.json")):
    d = json.loads(js.read_text(encoding="utf-8"))
    for key, e in d["sentences"].items():
        s = e["summary"]
        g = e.get("gpu_sampler") or {}
        print(f"| {d['backend']} | {key} | {s['first_chunk_ms_p50']} | {s['first_chunk_ms_max']} | {s['rtf_p50']} | "
              f"{s['audio_s_p50']} | {e.get('torch_max_allocated_mib')} | {g.get('gpu_mem_used_mib_max')} | "
              f"{'是' if s['streamed_all'] else '否'} | {d['started_at'][11:16]} |")