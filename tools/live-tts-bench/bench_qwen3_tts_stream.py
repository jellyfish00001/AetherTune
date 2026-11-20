"""Qwen3-TTS 自製串流：生成放背景執行緒，逐步攔截 talker 每步的 16 碼本 codec，
每累積 N 幀就用 12Hz tokenizer decoder（帶左側上下文，等同官方 chunked_decode 的作法）解碼送出。

qwen-tts 0.1.1 沒有串流生成 API；這是實驗性實作，不改套件檔，只在本行程包裝 talker.forward。
"""
import argparse
import queue
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--ref-src", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--ref-set", choices=sorted(common.REF_SETS), default="qwen-zh")
    ap.add_argument("--attn", choices=["sdpa", "flash_attention_2", "eager"], default="sdpa")
    ap.add_argument("--dtype", choices=["bf16", "fp16"], default="bf16")
    ap.add_argument("--first-frames", type=int, default=4, help="第一包幀數（12.5 幀/秒）")
    ap.add_argument("--chunk-frames", type=int, default=12)
    ap.add_argument("--left-context", type=int, default=25)
    ap.add_argument("--no-stream", action="store_true", help="不串流（原本整句生成），用來比較 attn/dtype")
    a = ap.parse_args()
    common.select_ref(a.ref_set)
    out = Path(a.out_dir)
    ref = str(common.prepare_ref(Path(a.ref_src), out))
    import torch
    from qwen_tts import Qwen3TTSModel

    dtype = torch.bfloat16 if a.dtype == "bf16" else torch.float16
    t = time.perf_counter()
    model = Qwen3TTSModel.from_pretrained(a.model_dir, device_map="cuda:0", dtype=dtype,
                                          attn_implementation=a.attn)
    prompt = model.create_voice_clone_prompt(ref_audio=ref, ref_text=common.REF_TEXT)
    load = time.perf_counter() - t
    core = model.model
    talker = core.talker
    dec = core.speech_tokenizer.model.decoder
    up = int(dec.total_upsample)
    sr = int(core.speech_tokenizer.get_output_sample_rate()) if hasattr(core.speech_tokenizer, "get_output_sample_rate") else 24000
    eos = core.config.talker_config.codec_eos_token_id
    ref_code = prompt[0].ref_code if isinstance(prompt, list) else None
    if ref_code is None and isinstance(prompt, dict):
        ref_code = prompt["ref_code"][0]

    box = {"q": None}
    orig_forward = talker.forward

    import functools

    @functools.wraps(orig_forward)  # 保留原簽名，HF generate 會檢查 forward 參數
    def wrapped(*args, **kw):
        o = orig_forward(*args, **kw)
        q = box["q"]
        if q is not None:
            hs = getattr(o, "hidden_states", None)
            if hs is not None and hs[-1] is not None:
                q.put(hs[-1].detach())
        return o
    talker.forward = wrapped

    def decode(codes_tq, ctx):
        # codes_tq: (T, Q) -> decoder 吃 (B, Q, T)
        with torch.inference_mode():
            wav = dec(codes_tq.clamp(min=0).T.unsqueeze(0).to(dec_device))
        return wav[0, 0, ctx * up:].float().cpu().numpy()
    dec_device = next(dec.parameters()).device

    def synth_stream(text):
        q = queue.Queue()
        box["q"] = q
        err = {}

        def run():
            try:
                with torch.inference_mode():
                    model.generate_voice_clone(text=text, language="Chinese", voice_clone_prompt=prompt)
            except Exception as e:  # noqa: BLE001
                err["e"] = e
            finally:
                q.put(None)
        # 串流時已自己分塊解碼；把套件最後的整句解碼換成空操作，避免重複解碼算進 RTF。
        st = core.speech_tokenizer
        real_decode = st.decode
        st.decode = lambda enc: ([__import__("numpy").zeros(16, dtype="float32") for _ in enc], sr)
        th = threading.Thread(target=run, daemon=True)
        th.start()
        frames = []
        emitted = 0
        prev = ref_code.to(dec_device) if ref_code is not None else None
        done = False
        while not done:
            item = q.get()
            if item is None:
                done = True
            else:
                c = item[0]
                if int(c[0]) == eos:
                    done = True
                else:
                    frames.append(c)
            need = a.first_frames if emitted == 0 else a.chunk_frames
            if frames and (len(frames) - emitted >= need or done):
                allf = torch.stack(frames)
                if prev is not None:
                    allf = torch.cat([prev, allf])
                    base = prev.shape[0]
                else:
                    base = 0
                start = base + emitted
                ctx = min(a.left_context, start)
                wav = decode(allf[start - ctx:], ctx)
                emitted = len(frames)
                yield wav
        th.join()
        st.decode = real_decode
        box["q"] = None
        if "e" in err:
            raise err["e"]

    def synth_full(text):
        wavs, _ = model.generate_voice_clone(text=text, language="Chinese", voice_clone_prompt=prompt)
        yield wavs[0]

    synth = synth_full if a.no_stream else synth_stream
    list(synth("你好"))
    size = Path(a.model_dir).name.replace("qwen3-tts-", "")
    name = f"qwen3-tts-{size}" + ("" if a.no_stream else f"-stream{a.first_frames}x{a.chunk_frames}")
    if a.attn != "sdpa":
        name += "-fa2" if a.attn == "flash_attention_2" else f"-{a.attn}"
    if a.dtype != "bf16":
        name += f"-{a.dtype}"
    common.run_bench(name, synth, sr, out,
                     {"package": "qwen-tts==0.1.1", "model": Path(a.model_dir).name, "dtype": a.dtype,
                      "attn": a.attn, "streaming": not a.no_stream, "first_frames": a.first_frames,
                      "chunk_frames": a.chunk_frames, "left_context": a.left_context,
                      "note": "自製串流：攔截 talker 每步 codec，分塊以 12Hz decoder 帶左側上下文解碼"},
                     Path(ref), load)


if __name__ == "__main__":
    main()
