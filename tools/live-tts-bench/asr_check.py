"""用 faster-whisper small（CPU int8）把各後端樣本 wav 轉寫回文字，算字錯率（CER）當可懂度粗檢。

只是粗檢：Whisper 可能輸出簡體，已用繁體提示詞偏向繁體；CER 會被同音字、簡繁差異拉高，需人工聽測確認。
在 PC1 WSL 的 D:\\AetherTune\\tools\\venvs\\stt-wsl 執行。
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

PUNCT = re.compile(r"[\s，。！？、,.!?…~「」『』：；:;\"'（）()]+")


def cer(ref: str, hyp: str) -> float:
    r, h = PUNCT.sub("", ref), PUNCT.sub("", hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev = cur
    return round(d[len(h)] / max(len(r), 1), 3)


def main():
    root = Path(sys.argv[1])
    from faster_whisper import WhisperModel

    model = WhisperModel("small", device="cpu", compute_type="int8")
    rows = []
    for wav in sorted(root.glob("*/*.wav")):
        if wav.parent.name == "ref":
            continue
        key = wav.stem.rsplit("-", 1)[-1]
        if key not in common.SENTENCES:
            continue
        segs, _ = model.transcribe(str(wav), language="zh", initial_prompt="以下是繁體中文的直播口語句子。")
        hyp = "".join(s.text for s in segs)
        rows.append({"wav": wav.name, "sentence": key, "hyp": hyp, "cer": cer(common.SENTENCES[key], hyp)})
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    (root / "asr-check.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()