#!/usr/bin/env python3
"""Synthesize ONE complete chapter with Doubao (Volcengine) TTS.

Voice, rate and cluster come from config.json `tts` (merged by user_config).
Credentials come ONLY from DOUBAO_APPID / DOUBAO_TOKEN and are never printed.

  python3 scripts/tts_doubao.py --narration-manifest planning/narration-manifest.json \
      --chapter 01 --output audio/01.wav
  python3 scripts/tts_doubao.py --text-file ch01.txt --output audio/01.wav --dry-run
"""

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import uuid
from pathlib import Path

from user_config import audio_profile, config_path

ENDPOINT = "https://openspeech.bytedance.com/api/v1/tts"


def chapter_text(args):
    if args.text_file:
        return Path(args.text_file).read_text(encoding="utf-8").strip()
    data = json.loads(Path(args.narration_manifest).read_text(encoding="utf-8"))
    for chapter in data.get("chapters", []):
        if str(chapter.get("chapterId")) == str(args.chapter):
            return str(chapter.get("narration", "")).strip()
    raise SystemExit(f"错误：narration manifest 里没有章节 {args.chapter}")


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text-file")
    source.add_argument("--narration-manifest")
    parser.add_argument("--chapter")
    parser.add_argument("--output", required=True)
    parser.add_argument("--dry-run", action="store_true", help="print the request (without credentials) and exit")
    args = parser.parse_args()
    if args.narration_manifest and not args.chapter:
        parser.error("--narration-manifest 需要同时提供 --chapter")

    tts = audio_profile()["tts"]
    voice = tts.get("voiceType")
    if not voice or "填你" in str(voice):
        print(f"错误：没有配置音色，请在 {config_path()} 的 tts.voiceType 填写火山引擎控制台里已开通的音色 ID", file=sys.stderr)
        return 2
    text = chapter_text(args)
    if not text:
        print("错误：章节口播为空", file=sys.stderr)
        return 2
    speed = round(1.0 + float(tts.get("ratePercent", 0)) / 100.0, 2)
    body = {
        "app": {"appid": "<DOUBAO_APPID>", "token": "<DOUBAO_TOKEN>", "cluster": tts.get("cluster", "volcano_tts")},
        "user": {"uid": "ip-course-videos"},
        "audio": {"voice_type": voice, "encoding": "mp3", "speed_ratio": speed},
        "request": {"reqid": str(uuid.uuid4()), "text": text, "text_type": "plain", "operation": "query"},
    }
    if args.dry_run:
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return 0

    appid, token = os.environ.get("DOUBAO_APPID"), os.environ.get("DOUBAO_TOKEN")
    if not appid or not token:
        print("错误：请先设置环境变量 DOUBAO_APPID 和 DOUBAO_TOKEN（不要写进配置文件）", file=sys.stderr)
        return 2
    body["app"]["appid"], body["app"]["token"] = appid, token
    request = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer;" + token})
    try:
        result = json.loads(urllib.request.urlopen(request, timeout=300).read())
    except Exception as exc:  # network errors must not echo the request body
        print(f"错误：豆包请求失败：{type(exc).__name__}", file=sys.stderr)
        return 1
    if result.get("code") != 3000 or not result.get("data"):
        print(f"错误：豆包合成失败 code={result.get('code')} message={result.get('message')}", file=sys.stderr)
        return 1

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    audio = base64.b64decode(result["data"])
    if output.suffix.lower() == ".mp3" or not shutil.which("ffmpeg"):
        output.write_bytes(audio)
    else:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as handle:
            handle.write(audio)
        try:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", handle.name,
                            "-ar", str(tts.get("sampleRateHz", 44100)), "-ac", str(tts.get("channels", 2)), str(output)], check=True)
        finally:
            os.unlink(handle.name)
    print(f"已合成：{output}（音色和语速来自配置，未打印密钥）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
