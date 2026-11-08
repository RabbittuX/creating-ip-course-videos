#!/usr/bin/env python3
"""Validate course manifests before preview approval and final rendering."""

import argparse
import json
import re
import sys
from pathlib import Path

from validate_aroll import load_json as load_aroll_json, validate_manifest as validate_aroll_manifest
from validate_broll import load_json as load_broll_json, validate_manifest as validate_broll_manifest
from validate_full_timeline import validate as validate_full_timeline


EDGE_PUNCTUATION = re.compile(r"^[，。！？；：、,.!?;:]|[，。！？；：、,.!?;:]$")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    manifest_path = Path(args.manifest)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = []

    previous_end = -1.0
    for index, cue in enumerate(sorted(data.get("captions", []), key=lambda x: x.get("start", 0))):
        text = str(cue.get("text", "")).strip()
        start = float(cue.get("start", 0))
        end = float(cue.get("end", 0))
        if not text:
            errors.append(f"字幕 {index + 1} 为空")
        if EDGE_PUNCTUATION.search(text):
            errors.append(f"字幕 {index + 1} 行首或行尾存在标点：{text}")
        if end <= start:
            errors.append(f"字幕 {index + 1} 时间无效：{start}-{end}")
        if start < previous_end:
            errors.append(f"字幕 {index + 1} 与上一条重叠")
        if float(cue.get("renderedWidthPx", 0)) > 1640:
            errors.append(f"字幕 {index + 1} 超过 1640px 安全宽度")
        previous_end = max(previous_end, end)

    for chapter in data.get("chapters", []):
        if chapter.get("state") in {"PREVIEW_APPROVED", "RENDERED", "FINAL_QC_PASSED"}:
            if chapter.get("previewBuildId") != chapter.get("approvedBuildId"):
                errors.append(f"章节 {chapter.get('id')} 的预览 build ID 与批准 build ID 不一致")
        if chapter.get("state") in {"RENDERED", "FINAL_QC_PASSED"} and not chapter.get("renderPath"):
            errors.append(f"章节 {chapter.get('id')} 缺少渲染文件路径")

    preview_states = {"PREVIEW_REVIEW", "PREVIEW_APPROVED", "RENDERED", "FINAL_QC_PASSED"}
    if any(chapter.get("state") in preview_states for chapter in data.get("chapters", [])):
        timeline_value = data.get("fullTimeline")
        if not timeline_value:
            errors.append("预览阶段必须声明 fullTimeline 完整父时间线")
        else:
            timeline_path = Path(timeline_value)
            if not timeline_path.is_absolute():
                timeline_path = manifest_path.parent / timeline_path
            if not timeline_path.is_file():
                errors.append(f"缺少完整父时间线：{timeline_path}")
            else:
                try:
                    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
                    errors.extend(f"父时间线：{error}" for error in validate_full_timeline(timeline, timeline_path.parent))
                except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                    errors.append(f"完整父时间线无法校验：{exc}")

    arroll_value = data.get("arollManifest")
    if arroll_value:
        arroll_path = Path(arroll_value)
        if not arroll_path.is_absolute():
            arroll_path = manifest_path.parent / arroll_path
        if not arroll_path.is_file():
            errors.append(f"缺少 A-roll 清单：{arroll_path}")
        else:
            profile_path = Path(__file__).resolve().parent.parent / "assets" / "presets" / "aroll-profile.json"
            mode = "preview" if any(ch.get("state") in preview_states for ch in data.get("chapters", [])) else "review"
            arroll_errors, arroll_warnings = validate_aroll_manifest(
                load_aroll_json(arroll_path), load_aroll_json(profile_path), mode
            )
            for warning in arroll_warnings:
                print(f"警告：A-roll：{warning}")
            errors.extend(f"A-roll：{error}" for error in arroll_errors)

    broll_value = data.get("brollManifest")
    if broll_value:
        broll_path = Path(broll_value)
        if not broll_path.is_absolute():
            broll_path = manifest_path.parent / broll_path
        if not broll_path.is_file():
            errors.append(f"缺少 B-roll 清单：{broll_path}")
        else:
            profile_path = Path(__file__).resolve().parent.parent / "assets" / "presets" / "broll-profile.json"
            mode = "preview" if any(ch.get("state") in preview_states for ch in data.get("chapters", [])) else "review"
            broll_errors, broll_warnings = validate_broll_manifest(
                load_broll_json(broll_path), load_broll_json(profile_path), mode
            )
            for warning in broll_warnings:
                print(f"警告：B-roll：{warning}")
            errors.extend(f"B-roll：{error}" for error in broll_errors)

    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    print("项目校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
