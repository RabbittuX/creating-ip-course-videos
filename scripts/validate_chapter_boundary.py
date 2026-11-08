#!/usr/bin/env python3
"""Validate the non-narrated fixed chapter-title interval."""

import argparse
import re
import sys
from pathlib import Path


def marked_tags(source, marker):
    return re.findall(rf"<[^>]+\b{re.escape(marker)}(?:=(?:\"[^\"]*\"|'[^']*'))?[^>]*>", source, re.I)


def number(tag, name):
    match = re.search(rf"\b{re.escape(name)}=[\"']([^\"']+)[\"']", tag, re.I)
    if not match:
        raise ValueError(f"缺少 {name}")
    return float(match.group(1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--composition", required=True)
    args = parser.parse_args()
    source = Path(args.composition).read_text(encoding="utf-8")
    errors = []
    titles = marked_tags(source, "data-chapter-title-broll")
    narrations = marked_tags(source, "data-narration-track")
    stings = marked_tags(source, "data-chapter-sting")
    if len(titles) != 1:
        errors.append("必须且只能有一个章节页 data-chapter-title-broll")
    if len(narrations) != 1:
        errors.append("必须且只能有一个旁白轨 data-narration-track")
    if len(stings) != 1:
        errors.append("必须且只能有一个章节页专属音效 data-chapter-sting")
    if not errors:
        try:
            title_start = number(titles[0], "data-start")
            title_end = title_start + number(titles[0], "data-duration")
            narration_start = number(narrations[0], "data-start")
            sting_start = number(stings[0], "data-start")
            sting_end = sting_start + number(stings[0], "data-duration")
            if abs(title_start) > 1e-6:
                errors.append("章节页必须从 0 秒开始")
            if narration_start < title_end - 1e-6:
                errors.append("旁白不得与章节页重叠；必须从章节页结束后开始")
            if sting_start < title_start - 1e-6 or sting_end > title_end + 1e-6:
                errors.append("章节页专属音效必须完整位于章节页区间内")
            caption_tags = re.findall(r"<[^>]+class=[\"'][^\"']*\bcaption\b[^\"']*[\"'][^>]*>", source, re.I)
            if any(number(tag, "data-start") < title_end - 1e-6 for tag in caption_tags):
                errors.append("字幕不得出现在章节页区间内")
        except ValueError as exc:
            errors.append(str(exc))
    for scene in re.findall(r"<section[^>]+data-aroll-scene[^>]*>.*?</section>", source, re.I | re.S):
        if "data-aroll-paper" not in scene or "data-aroll-stage" not in scene:
            errors.append("A-roll 必须同时包含锁定的画面背景 data-aroll-paper 和屏幕背景 data-aroll-stage")
            break
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("章节页音频边界校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
