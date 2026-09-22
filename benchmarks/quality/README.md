# Acoustic Objective Benchmark

這一層延續 `tools/audio-quality-batch.py` 的 signal-level 檢查：decode、finite、non-zero、sample rate、RMS、peak、silence、DC、clipping 與 hash。

它不能單獨推導 MOS、自然度、聲線相似度或情緒保留。正式比較要先決定同一重取樣與 loudness policy，並保留未正規化原始輸出供回溯。
