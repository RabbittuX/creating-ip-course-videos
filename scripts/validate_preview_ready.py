#!/usr/bin/env python3
"""Validate the complete parent timeline before PREVIEW_READY."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from validate_full_timeline import validate as validate_full_timeline
from validate_visual_assembly import validate as validate_visual_assembly


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve(base, value):
    path = Path(value)
    return path if path.is_absolute() else base / path


def validate(project_root, chapter_id, build_id=None):
    root = Path(project_root).resolve()
    project_path = root / "project.json"
    evidence = {"chapterId": str(chapter_id)}
    errors = []
    if not project_path.is_file():
        return evidence, ["缺少 project.json"]
    project = json.loads(project_path.read_text(encoding="utf-8"))
    visual_assembly_value = project.get("visualAssembly")
    visual_assembly_path = resolve(root, visual_assembly_value).resolve() if visual_assembly_value else None
    if not visual_assembly_path or not visual_assembly_path.is_file():
        errors.append("project.json 未声明可校验的 visualAssembly，禁止直接拼装预览")
    else:
        assembly_evidence, assembly_errors = validate_visual_assembly(visual_assembly_path)
        errors.extend(f"画面组装：{error}" for error in assembly_errors)
        evidence["visualAssembly"] = assembly_evidence
    expected_chapters = [str(item.get("id")) for item in project.get("chapters", [])]
    timeline_value = project.get("fullTimeline")
    if not timeline_value:
        return evidence, ["project.json 未声明完整父时间线 fullTimeline"]
    timeline_path = Path(timeline_value)
    timeline_path = timeline_path if timeline_path.is_absolute() else root / timeline_path
    if not timeline_path.is_file():
        return evidence, [f"缺少完整父时间线：{timeline_path}"]
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    errors.extend(validate_full_timeline(timeline, timeline_path.parent))
    if timeline.get("status") != "READY":
        errors.append("完整父时间线尚未标记为 READY")
    actual_chapters = [str(item.get("chapterId", item.get("id", ""))) for item in timeline.get("chapters", [])]
    if actual_chapters != expected_chapters:
        errors.append(f"完整父时间线必须按顺序包含全部章节：期望 {expected_chapters}，实际 {actual_chapters}")
    if not any(str(item.get("chapterId", item.get("id", ""))) == str(chapter_id) for item in timeline.get("chapters", [])):
        errors.append(f"完整父时间线缺少章节 {chapter_id}")
    approvals_path = root / "approvals.json"
    if approvals_path.is_file():
        approvals = json.loads(approvals_path.read_text(encoding="utf-8"))
        for cid in expected_chapters:
            if not (approvals.get("chapters", {}).get(cid, {}).get("milestones", {}).get("broll-sync")):
                errors.append(f"章节 {cid} 尚未达到 BROLL_SYNC_READY")
    preview_manifest = root / "preview" / "preview-ready.json"
    if not preview_manifest.is_file():
        errors.append("缺少预览产物证据 preview-ready.json")
        evidence.update({"timelinePath": str(timeline_path), "timelineHash": digest(timeline_path)})
        return evidence, errors
    preview = json.loads(preview_manifest.read_text(encoding="utf-8"))
    if preview.get("status") != "READY":
        errors.append("预览产物尚未标记为 READY")
    if build_id and preview.get("buildId") != build_id:
        errors.append("预览产物 buildId 与待标记版本不一致")
    for field, hash_field, label in (("compositionPath", "compositionHash", "预览组合"), ("fullTimelinePath", "fullTimelineHash", "父时间线")):
        value = preview.get(field)
        target = resolve(preview_manifest.parent, value).resolve() if value else None
        if not target or not target.is_file():
            errors.append(f"{label}文件不存在")
        elif preview.get(hash_field) != digest(target):
            errors.append(f"{label}{hash_field} 与当前文件不匹配")
    for field, hash_field, label, project_value in (
        ("creativeDirectivesPath", "creativeDirectivesHash", "创意指令", project.get("creativeDirectives")),
        ("brollManifestPath", "brollManifestHash", "B-roll 正式清单", project.get("brollManifest")),
        ("visualAssemblyPath", "visualAssemblyHash", "画面组装清单", project.get("visualAssembly")),
    ):
        value = preview.get(field)
        target = resolve(preview_manifest.parent, value).resolve() if value else None
        expected = resolve(root, project_value).resolve() if project_value else None
        if not target or not target.is_file():
            errors.append(f"预览产物缺少{label}文件或哈希绑定")
        elif target != expected or preview.get(hash_field) != digest(target):
            errors.append(f"预览产物{label}哈希与当前项目不一致")
    if preview.get("fullTimelineHash") != digest(timeline_path):
        errors.append("预览产物不是基于当前完整父时间线生成")
    evidence.update({"timelinePath": str(timeline_path), "timelineHash": digest(timeline_path), "previewManifestPath": str(preview_manifest), "previewManifestHash": digest(preview_manifest), "previewBuildId": preview.get("buildId"), "creativeDirectivesHash": preview.get("creativeDirectivesHash"), "brollManifestHash": preview.get("brollManifestHash")})
    return evidence, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--build-id")
    args = parser.parse_args()
    try:
        evidence, errors = validate(args.project_root, args.chapter, args.build_id)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"错误：PREVIEW_READY 无法校验：{exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    print(json.dumps(evidence, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
