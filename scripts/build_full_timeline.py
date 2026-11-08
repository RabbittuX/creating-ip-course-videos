#!/usr/bin/env python3
"""Assemble chapter-local timing specifications into one parent timeline."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from validate_full_timeline import validate


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def shifted(window, offset):
    if not window:
        return None
    return {**window, "startMs": float(window["startMs"]) + offset, "endMs": float(window["endMs"]) + offset}


def build(project_root):
    root = Path(project_root).resolve()
    project = json.loads((root / "project.json").read_text(encoding="utf-8"))
    chapters, errors, cursor = [], [], 0.0
    for entry in project.get("chapters", []):
        cid = str(entry.get("id"))
        spec_path = root / "chapters" / cid / "timing" / "chapter-timeline.json"
        if not spec_path.is_file():
            errors.append(f"章节 {cid} 缺少 chapter-timeline.json")
            continue
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        duration = float(spec.get("durationMs", 0) or 0)
        if duration <= 0:
            errors.append(f"章节 {cid} 的 durationMs 无效")
            continue
        chapter = {
            "chapterId": cid,
            "startMs": cursor,
            "endMs": cursor + duration,
            "titleWindow": shifted(spec.get("titleWindow"), cursor),
            "stingWindow": shifted(spec.get("stingWindow"), cursor),
            "narrationWindow": shifted(spec.get("narrationWindow"), cursor),
            "captions": [shifted(cue, cursor) for cue in spec.get("captions", [])],
            "sourcePath": str(spec_path.relative_to(root)),
            "sourceHash": digest(spec_path),
        }
        if spec.get("captionTrack"):
            chapter["captionTrack"] = {**spec["captionTrack"], "parentOffsetMs": cursor + float(spec["captionTrack"].get("parentOffsetMs", 0) or 0)}
        chapters.append(chapter)
        cursor += duration
    result = {"schemaVersion": 1, "projectId": project.get("projectId"), "status": "READY", "durationMs": cursor, "chapters": chapters}
    errors.extend(validate(result, root))
    return result, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result, errors = build(args.project_root)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"错误：完整父时间线无法生成：{exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    target = Path(args.output) if args.output else Path(args.project_root).resolve() / "timing" / "full-timeline.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已生成完整父时间线：{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
