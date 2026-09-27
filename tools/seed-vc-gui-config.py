"""Read PortAudio devices and prepare Seed-VC's normal GUI settings file.

This helper does not open an audio stream or change Windows default devices.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def select_device_pair(
    hostapis: list[dict[str, Any]],
    devices: list[dict[str, Any]],
    host_api_name: str | None,
    input_name: str | None,
    output_name: str | None,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Require one unambiguous input/output pair within a single PortAudio host API."""

    if not input_name or not output_name:
        raise ValueError("輸入和輸出裝置名稱都必須明確設定，或先提供已保存的 GUI 設定。")
    api_names = [str(item.get("name", "")) for item in hostapis]
    if host_api_name:
        if host_api_name not in api_names:
            raise ValueError(f"找不到 Host API: {host_api_name}")
        candidate_apis = [host_api_name]
    else:
        candidate_apis = api_names

    pairs: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for api_name in candidate_apis:
        inputs = [
            item for item in devices
            if item.get("hostapi_name") == api_name
            and str(item.get("name", "")) == input_name
            and int(item.get("max_input_channels", 0)) > 0
        ]
        outputs = [
            item for item in devices
            if item.get("hostapi_name") == api_name
            and str(item.get("name", "")) == output_name
            and int(item.get("max_output_channels", 0)) > 0
        ]
        for input_device in inputs:
            for output_device in outputs:
                pairs.append((api_name, input_device, output_device))

    if not pairs:
        raise ValueError(
            "找不到同一 Host API 下符合方向與名稱的裝置組合；請用 --list-devices 查看 PortAudio 列舉結果。"
        )
    if len(pairs) != 1:
        rendered = "; ".join(
            f"{api}: input #{source.get('index')} / output #{sink.get('index')}"
            for api, source, sink in pairs
        )
        raise ValueError(f"裝置名稱有歧義，請同時指定 --host-api。候選：{rendered}")
    return pairs[0]


def validate_reference(path_value: str | Path) -> Path:
    """Require an existing reference at an ASCII-only absolute path for upstream GUI compatibility."""

    reference = Path(path_value).expanduser().resolve()
    if not reference.is_file():
        raise ValueError(f"reference audio 不存在：{reference}")
    if any(ord(character) > 127 for character in str(reference)):
        raise ValueError("Seed-VC 官方 GUI 不接受含非 ASCII 字元的 reference path；請移至純 ASCII 路徑。")
    return reference


def _read_config(path: Path, defaults_path: Path) -> dict[str, Any]:
    source = path if path.is_file() else defaults_path
    if not source.is_file():
        raise FileNotFoundError(f"Seed-VC GUI 設定範本不存在：{defaults_path}")
    try:
        data = json.loads(source.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"無法讀取 Seed-VC GUI 設定 {source}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Seed-VC GUI 設定根節點不是 JSON object：{source}")
    return data


def _enumerate_devices() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        import sounddevice as sd
    except Exception as exc:
        raise RuntimeError(f"無法載入 Seed-VC venv 的 sounddevice：{type(exc).__name__}: {exc}") from exc
    hostapis = [dict(item) for item in sd.query_hostapis()]
    devices = [dict(item) for item in sd.query_devices()]
    for item in devices:
        api_index = item.get("hostapi")
        item["hostapi_name"] = (
            str(hostapis[int(api_index)].get("name", ""))
            if isinstance(api_index, int) and 0 <= api_index < len(hostapis)
            else ""
        )
    return hostapis, devices


def _print_devices(hostapis: list[dict[str, Any]], devices: list[dict[str, Any]]) -> None:
    print("PortAudio 裝置清單（唯讀；沒有開啟 stream）：")
    if not devices:
        print("  WAITING: 沒有列舉到音訊裝置。")
    for item in devices:
        direction = []
        if int(item.get("max_input_channels", 0)) > 0:
            direction.append("input")
        if int(item.get("max_output_channels", 0)) > 0:
            direction.append("output")
        print(
            f"  #{item.get('index')} [{item.get('hostapi_name')}] "
            f"{','.join(direction) or 'no-audio'} | {item.get('name')} | "
            f"in={item.get('max_input_channels')} out={item.get('max_output_channels')}"
        )
    print("Host API:")
    for index, item in enumerate(hostapis):
        print(f"  #{index} {item.get('name')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--host-api")
    parser.add_argument("--input-device")
    parser.add_argument("--output-device")
    parser.add_argument("--reference-audio", type=Path)
    parser.add_argument("--list-devices", action="store_true")
    args = parser.parse_args()

    repo = args.repo.resolve()
    gui_config_path = repo / "configs" / "inuse" / "config.json"
    defaults_path = repo / "configs" / "config.json"
    if not (repo / "real-time-gui.py").is_file() or not defaults_path.is_file():
        print("BLOCKED: Seed-VC upstream GUI or configs/config.json is missing.")
        return 2
    try:
        hostapis, devices = _enumerate_devices()
        if args.list_devices:
            _print_devices(hostapis, devices)
            return 0 if devices else 3

        settings = _read_config(gui_config_path, defaults_path)
        selected_api = args.host_api or settings.get("sg_hostapi") or None
        selected_input = args.input_device or settings.get("sg_input_device") or None
        selected_output = args.output_device or settings.get("sg_output_device") or None
        api_name, input_device, output_device = select_device_pair(
            hostapis, devices, selected_api, selected_input, selected_output
        )

        reference = args.reference_audio
        if reference is not None:
            reference = validate_reference(reference)
            settings["reference_audio_path"] = str(reference)
        else:
            saved_reference = settings.get("reference_audio_path")
            if isinstance(saved_reference, str) and saved_reference.strip():
                settings["reference_audio_path"] = str(validate_reference(saved_reference))

        settings["sg_hostapi"] = api_name
        settings["sg_input_device"] = str(input_device["name"])
        settings["sg_output_device"] = str(output_device["name"])
        settings.setdefault("sg_wasapi_exclusive", False)
        gui_config_path.parent.mkdir(parents=True, exist_ok=True)
        gui_config_path.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("PASS: 設定 Seed-VC 官方 GUI 的 PortAudio 裝置；未啟動 stream，也未改 Windows 預設裝置。")
        print(f"Host API: {api_name}")
        print(f"Input #{input_device.get('index')}: {input_device['name']}")
        print(f"Output #{output_device.get('index')}: {output_device['name']}")
        print(f"Reference: {settings.get('reference_audio_path') or '(請在 GUI 選擇授權 reference audio)'}")
        print(f"GUI settings: {gui_config_path}")
        return 0
    except Exception as exc:
        print(f"BLOCKED: {type(exc).__name__}: {exc}")
        if not args.list_devices:
            print("先執行 tools\\seed-vc-gui-run.ps1 -ListDevices，再用 -HostApi、-InputDevice、-OutputDevice 明確選擇裝置。")
        return 2


if __name__ == "__main__":
    sys.exit(main())
