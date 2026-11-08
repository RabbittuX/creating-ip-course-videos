#!/usr/bin/env python3
"""Compare planned A/B-roll durations with word-aligned narration time."""

import argparse
import json
import sys
from pathlib import Path


def kind(scene):
    return str(scene.get("type", "")).lower().replace("-", "")


def stats(scenes, duration_key):
    ar = sum(float(item.get(duration_key, 0) or 0) for item in scenes if kind(item) == "aroll")
    br = sum(float(item.get(duration_key, 0) or 0) for item in scenes if kind(item) == "broll")
    total = ar + br
    return {"totalSeconds": round(total, 3), "aroll": {"seconds": round(ar, 3), "ratio": round(ar / total, 4) if total else 0}, "broll": {"seconds": round(br, 3), "ratio": round(br / total, 4) if total else 0}}


def build(project_root, chapter_id=None):
    root = Path(project_root).resolve()
    outline = json.loads((root / "planning" / "visual-outline.json").read_text(encoding="utf-8"))
    report_path = root / "planning" / "actual-duration-report.json"
    previous = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {"schemaVersion": 1, "chapters": []}
    reports = {str(item.get("chapterId")): item for item in previous.get("chapters", [])}
    errors = []
    for chapter in outline.get("chapters", []):
        cid = str(chapter.get("chapterId", chapter.get("id", "")))
        if chapter_id is not None and cid != str(chapter_id):
            continue
        alignment_path = root / "chapters" / cid / "audio" / "alignment.json"
        if not alignment_path.is_file():
            errors.append(f"章节 {cid} 缺少词级对齐，无法计算实际时长")
            continue
        alignment = json.loads(alignment_path.read_text(encoding="utf-8"))
        tokens = alignment.get("tokens") or []
        scene_reports = []
        measured_scenes = []
        chapter_review = False
        for scene in chapter.get("scenes", []):
            start, end = scene.get("sourceCharStart"), scene.get("sourceCharEnd")
            sid = str(scene.get("sceneId", scene.get("id", "")))
            if not isinstance(start, int) or not isinstance(end, int) or end <= start:
                errors.append(f"章节 {cid} / {sid} 缺少有效口播字符范围")
                continue
            overlapping = [item for item in tokens if isinstance(item.get("charStart"), (int, float)) and isinstance(item.get("charEnd"), (int, float)) and item["charEnd"] > start and item["charStart"] < end]
            if not overlapping:
                errors.append(f"章节 {cid} / {sid} 没有对应词级时间")
                continue
            actual = (float(overlapping[-1]["endMs"]) - float(overlapping[0]["startMs"])) / 1000
            planned = float(scene.get("plannedDurationSeconds", 0) or 0)
            drift = actual - planned
            needs_review = abs(drift) > 1.0
            chapter_review = chapter_review or needs_review
            measured = dict(scene)
            measured["actualDurationSeconds"] = actual
            measured_scenes.append(measured)
            scene_reports.append({"sceneId": sid, "type": scene.get("type"), "plannedDurationSeconds": planned, "actualDurationSeconds": round(actual, 3), "driftSeconds": round(drift, 3), "reviewRequired": needs_review})
        planned_stats = stats(chapter.get("scenes", []), "plannedDurationSeconds")
        actual_stats = stats(measured_scenes, "actualDurationSeconds")
        ratio_drift = max(abs(float(actual_stats[name]["ratio"]) - float(planned_stats[name]["ratio"])) for name in ("aroll", "broll"))
        if ratio_drift > 0.05:
            chapter_review = True
        reports[cid] = {"chapterId": cid, "status": "REVIEW_REQUIRED" if chapter_review else "PASS", "scenes": scene_reports, "plannedStats": planned_stats, "actualStats": actual_stats, "maxRatioDrift": round(ratio_drift, 4)}
        if chapter_review:
            errors.append(f"章节 {cid} 实际时长偏差超过 1 秒或 A/B-roll 占比偏差超过 5%，必须重新审核视觉梗概")
    ordered = []
    project = json.loads((root / "project.json").read_text(encoding="utf-8"))
    for entry in project.get("chapters", []):
        cid = str(entry.get("id"))
        if cid in reports:
            ordered.append(reports[cid])
    result = {"schemaVersion": 1, "status": "REVIEW_REQUIRED" if any(item.get("status") == "REVIEW_REQUIRED" for item in ordered) else "PASS", "thresholds": {"sceneDriftSeconds": 1.0, "ratioDrift": 0.05}, "chapters": ordered}
    return result, errors


def write_report(project_root, chapter_id=None, output=None):
    result, errors = build(project_root, chapter_id)
    target = Path(output) if output else Path(project_root).resolve() / "planning" / "actual-duration-report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target, result, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--chapter")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        target, _, errors = write_report(args.project_root, args.chapter, args.output)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"错误：实际时长报告无法生成：{exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    print(f"已生成实际时长报告：{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
