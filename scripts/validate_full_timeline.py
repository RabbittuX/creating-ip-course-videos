#!/usr/bin/env python3
"""Validate captions and narration on the complete parent timeline."""

import argparse
import json
import sys
from pathlib import Path

from validate_captions import validate as validate_caption_file


def overlaps(left, right):
    return float(left["startMs"]) < float(right["endMs"]) and float(right["startMs"]) < float(left["endMs"])


def inside(window, outer):
    return float(window["startMs"]) >= float(outer["startMs"]) and float(window["endMs"]) <= float(outer["endMs"])


def validate(data, base_dir):
    errors = []
    duration = float(data.get("durationMs", 0) or 0)
    previous_end = 0
    chapters = sorted(data.get("chapters", []), key=lambda item: float(item.get("startMs", 0)))
    if not chapters:
        errors.append("父时间线没有章节")
    for chapter in chapters:
        cid = chapter.get("chapterId", chapter.get("id", "<unknown>"))
        window = {"startMs": float(chapter.get("startMs", -1)), "endMs": float(chapter.get("endMs", -1))}
        if window["startMs"] < previous_end:
            errors.append(f"章节 {cid} 与上一章节在父时间线上重叠")
        if window["endMs"] <= window["startMs"] or (duration and window["endMs"] > duration):
            errors.append(f"章节 {cid} 的父时间线范围无效")
        title = chapter.get("titleWindow")
        sting = chapter.get("stingWindow")
        narration = chapter.get("narrationWindow")
        if title:
            if not inside(title, window):
                errors.append(f"章节 {cid} 的章节页超出章节范围")
            if not sting or not inside(sting, title):
                errors.append(f"章节 {cid} 的章节页提示音必须完整位于章节页内")
            if narration and overlaps(title, narration):
                errors.append(f"章节 {cid} 的正文口播不得混入章节页")
        if narration and not inside(narration, window):
            errors.append(f"章节 {cid} 的正文口播超出章节范围")
        inline_captions = list(chapter.get("captions", []))
        caption_ref = chapter.get("captionTrack") or {}
        caption_path_value = caption_ref.get("captionsPath")
        if caption_path_value:
            caption_path = Path(caption_path_value)
            if not caption_path.is_absolute():
                caption_path = base_dir / caption_path
            alignment_path = Path(caption_ref.get("alignmentPath", ""))
            audio_path = Path(caption_ref.get("audioPath", ""))
            narration_value = caption_ref.get("narrationPath")
            narration_path = Path(narration_value) if narration_value else None
            if not alignment_path.is_absolute():
                alignment_path = base_dir / alignment_path
            if not audio_path.is_absolute():
                audio_path = base_dir / audio_path
            if narration_path is not None and not narration_path.is_absolute():
                narration_path = base_dir / narration_path
            if not caption_path.is_file() or not alignment_path.is_file() or not audio_path.is_file():
                errors.append(f"章节 {cid} 缺少字幕、对齐或音频产物")
            else:
                caption_data = json.loads(caption_path.read_text(encoding="utf-8"))
                alignment_data = json.loads(alignment_path.read_text(encoding="utf-8"))
                errors.extend(f"章节 {cid}：{error}" for error in validate_caption_file(caption_data, alignment_data, alignment_path, audio_path, narration_path))
                shift = float(caption_ref.get("parentOffsetMs", 0) or 0)
                inline_captions.extend({**cue, "startMs": float(cue["startMs"]) + shift, "endMs": float(cue["endMs"]) + shift} for cue in caption_data.get("captions", []))
        previous_caption_end = -1
        for cue in sorted(inline_captions, key=lambda item: float(item.get("startMs", 0))):
            cue_window = {"startMs": float(cue.get("startMs", -1)), "endMs": float(cue.get("endMs", -1))}
            if not inside(cue_window, window):
                errors.append(f"章节 {cid} 的字幕 {cue.get('id', '')} 超出章节范围")
            if title and overlaps(cue_window, title):
                errors.append(f"章节 {cid} 的章节页不得出现正文字幕")
            if narration and not inside(cue_window, narration):
                errors.append(f"章节 {cid} 的字幕不在正文口播区间内")
            if cue_window["startMs"] < previous_caption_end:
                errors.append(f"章节 {cid} 的父时间线字幕重叠")
            previous_caption_end = max(previous_caption_end, cue_window["endMs"])
        previous_end = max(previous_end, window["endMs"])
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeline", required=True)
    args = parser.parse_args()
    path = Path(args.timeline)
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate(data, path.parent)
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    print("完整父时间线校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
