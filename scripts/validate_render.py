#!/usr/bin/env python3
"""Run deterministic media probes for black frames and unexpected silence."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def command(args):
    return subprocess.run(args, text=True, capture_output=True)


def frame_rate(value):
    try:
        numerator, denominator = str(value).split("/", 1)
        return float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        return 0


def validate_probe(probe, profile):
    errors = []
    expected = profile["upload"]
    video = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in probe.get("streams", []) if stream.get("codec_type") == "audio"), None)
    if not video:
        errors.append("缺少视频流")
    else:
        if video.get("codec_name") != "h264": errors.append("上传版视频编码必须为 H.264")
        if (int(video.get("width", 0)), int(video.get("height", 0))) != (expected["width"], expected["height"]): errors.append("上传版分辨率必须为 1920×1080")
        if abs(frame_rate(video.get("avg_frame_rate")) - float(expected["fps"])) > 0.01: errors.append("上传版帧率必须为 30fps")
        if video.get("pix_fmt") != expected["video"]["pixelFormat"]: errors.append("上传版像素格式必须为 yuv420p")
    if not audio:
        errors.append("缺少音频流")
    else:
        if audio.get("codec_name") != expected["audio"]["codec"]: errors.append("上传版音频编码必须为 AAC")
        if int(audio.get("sample_rate", 0)) != int(expected["audio"]["sampleRateHz"]): errors.append("上传版音频采样率必须为 48kHz（48000Hz）")
        if int(audio.get("channels", 0)) != 2: errors.append("上传版音频必须为双声道")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--profile", default=str(Path(__file__).resolve().parent.parent / "assets" / "presets" / "delivery-profile.json"))
    parser.add_argument("--allow-silence", action="store_true")
    args = parser.parse_args()
    video = Path(args.video).resolve()
    if not video.is_file():
        print(f"错误：视频不存在：{video}", file=sys.stderr)
        return 2
    probe = command(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)])
    scan = command(["ffmpeg", "-hide_banner", "-i", str(video), "-vf", "blackdetect=d=0.15:pix_th=0.10", "-af", "silencedetect=n=-45dB:d=0.8", "-f", "null", "-"])
    white_scan = command(["ffmpeg", "-hide_banner", "-i", str(video), "-vf", "negate,blackdetect=d=0.08:pix_th=0.04", "-an", "-f", "null", "-"])
    if probe.returncode:
        print(probe.stderr, file=sys.stderr)
        return 2
    black = [line.strip() for line in scan.stderr.splitlines() if "black_start:" in line]
    white = [line.strip() for line in white_scan.stderr.splitlines() if "black_start:" in line]
    silence = [line.strip() for line in scan.stderr.splitlines() if "silence_start:" in line]
    probe_data = json.loads(probe.stdout)
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    errors = validate_probe(probe_data, profile)
    video_hash = hashlib.sha256(video.read_bytes()).hexdigest()
    report = {"schemaVersion": 2, "status": "PASSED", "video": str(video), "videoHash": video_hash, "profile": str(Path(args.profile).resolve()), "probe": probe_data, "blackEvents": black, "whiteFlashEvents": white, "silenceEvents": silence}
    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if black:
        errors.append(f"检测到 {len(black)} 个黑屏区间")
    if white:
        errors.append(f"检测到 {len(white)} 个白闪区间")
    if silence and not args.allow_silence:
        errors.append(f"检测到 {len(silence)} 个未豁免静音区间")
    if errors:
        report["status"] = "FAILED"
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    print("渲染媒体检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
