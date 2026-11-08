#!/usr/bin/env python3
"""Validate concise A/B-roll design, narration spans, previews, and ratios."""

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

from narration_contract import validate_manifest as validate_narration_manifest


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve(base, value):
    path = Path(value)
    return path if path.is_absolute() else base / path


def ratio_stats(scenes):
    ar = sum(float(item.get("plannedDurationSeconds", 0) or 0) for item in scenes if str(item.get("type", "")).lower().replace("-", "") == "aroll")
    br = sum(float(item.get("plannedDurationSeconds", 0) or 0) for item in scenes if str(item.get("type", "")).lower().replace("-", "") == "broll")
    total = ar + br
    return {"totalSeconds": round(total, 3), "aroll": {"seconds": round(ar, 3), "ratio": round(ar / total, 4) if total else 0}, "broll": {"seconds": round(br, 3), "ratio": round(br / total, 4) if total else 0}}


def same_stats(left, right):
    try:
        return all(math.isclose(float(left[k][sub]), float(right[k][sub]), abs_tol=0.001) for k in ("aroll", "broll") for sub in ("seconds", "ratio")) and math.isclose(float(left["totalSeconds"]), float(right["totalSeconds"]), abs_tol=0.001)
    except (KeyError, TypeError, ValueError):
        return False


def validate_file(base, value, expected_hash, label, errors):
    if not value:
        errors.append(f"{label} 缺少路径")
        return
    path = resolve(base, value).resolve()
    if not path.is_file():
        errors.append(f"{label} 文件不存在：{path}")
    elif not expected_hash or digest(path) != expected_hash:
        errors.append(f"{label} 哈希缺失或不匹配")


def validate(outline_path, chapter_id=None, project_root=None):
    path = Path(outline_path).resolve()
    base = Path(project_root).resolve() if project_root else path.parent.parent
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    if data.get("status") not in {"REVIEW_READY", "APPROVED"}:
        errors.append("视觉梗概必须标记为 REVIEW_READY")
    all_chapters = data.get("chapters", [])
    chapters = [item for item in all_chapters if chapter_id is None or str(item.get("chapterId", item.get("id", ""))) == str(chapter_id)]
    if not chapters:
        errors.append(f"视觉梗概缺少章节 {chapter_id}" if chapter_id else "视觉梗概没有章节")
    for chapter in chapters:
        cid = str(chapter.get("chapterId", chapter.get("id", "")))
        narration = str(chapter.get("narration", ""))
        narration_manifest = base / "planning" / "narration-manifest.json"
        if narration_manifest.is_file():
            narration_evidence, narration_errors = validate_narration_manifest(base, cid)
            errors.extend(f"章节 {cid}：{error}" for error in narration_errors)
            if not narration_errors and narration != narration_evidence.get("canonicalNarration"):
                errors.append(f"章节 {cid} 视觉梗概口播与唯一主口播不一致")
        scenes = chapter.get("scenes") or []
        if not narration or not scenes:
            errors.append(f"章节 {cid} 缺少口播或镜头")
            continue
        ids = set()
        for index, scene in enumerate(scenes, 1):
            sid = str(scene.get("sceneId", scene.get("id", "")))
            label = f"章节 {cid} / 镜头 {sid or index}"
            if not sid or sid in ids:
                errors.append(f"{label} sceneId 缺失或重复")
            ids.add(sid)
            kind = str(scene.get("type", "")).lower().replace("-", "")
            if kind not in {"aroll", "broll"}:
                errors.append(f"{label} type 必须为 A-roll 或 B-roll")
            summary = str(scene.get("summary", "")).strip()
            if not summary or len(summary) > 40:
                errors.append(f"{label} 梗概必须精简且不超过 40 字")
            source = str(scene.get("sourceText", ""))
            start, end = scene.get("sourceCharStart"), scene.get("sourceCharEnd")
            if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start or end > len(narration) or narration[start:end] != source:
                errors.append(f"{label} 真实口播字符范围不匹配")
            if float(scene.get("plannedDurationSeconds", 0) or 0) <= 0:
                errors.append(f"{label} 缺少计划时长")
            if not str(scene.get("rationale", "")).strip():
                errors.append(f"{label} 缺少 A/B-roll 选择理由")
            if kind == "aroll":
                for field in ("backgroundId", "castIds", "actorAction"):
                    if not scene.get(field):
                        errors.append(f"{label} A-roll 缺少 {field}")
            if kind == "broll":
                origin, mode = scene.get("designOrigin"), scene.get("progressMode")
                if origin not in {"template", "custom"}:
                    errors.append(f"{label} designOrigin 必须为 template 或 custom")
                if mode not in {"static", "narration-driven"}:
                    errors.append(f"{label} progressMode 必须为 static 或 narration-driven")
                if origin == "template":
                    for field in ("templateId", "templateVersion"):
                        if not scene.get(field):
                            errors.append(f"{label} 模板 B-roll 缺少 {field}")
                    validate_file(base, scene.get("previewPath"), scene.get("previewHash"), f"{label} 模板预览", errors)
                elif origin == "custom":
                    validate_file(base, scene.get("designPreviewPath"), scene.get("designPreviewHash"), f"{label} 自定义设计预览", errors)
                    validate_file(base, scene.get("layoutSpecPath"), scene.get("layoutSpecHash"), f"{label} 自定义布局规格", errors)
                if mode == "narration-driven":
                    items = scene.get("items") or []
                    if not items:
                        errors.append(f"{label} 口播驱动画面缺少 items")
                    for item in items:
                        if not item.get("itemId") or not item.get("label") or not str(item.get("sourceText", "")).strip():
                            errors.append(f"{label} 流程项缺少 itemId/label/sourceText")
        ordered = sorted(scenes, key=lambda item: int(item.get("sourceCharStart", -1)) if isinstance(item.get("sourceCharStart"), int) else -1)
        cursor = 0
        for scene in ordered:
            start, end = scene.get("sourceCharStart"), scene.get("sourceCharEnd")
            if isinstance(start, int) and isinstance(end, int):
                if start != cursor:
                    errors.append(f"章节 {cid} 镜头范围未连续完整覆盖主口播：期望从字符 {cursor} 开始，实际为 {start}")
                    break
                cursor = end
        if ordered and cursor != len(narration):
            errors.append(f"章节 {cid} 镜头范围未完整覆盖主口播：覆盖到 {cursor}/{len(narration)}")
        expected = ratio_stats(scenes)
        if not same_stats(chapter.get("stats", {}), expected):
            errors.append(f"章节 {cid} A/B-roll 时长统计或占比不正确")
    expected_overall = ratio_stats([scene for chapter in all_chapters for scene in (chapter.get("scenes") or [])])
    if not same_stats(data.get("overallStats", {}), expected_overall):
        errors.append("全片 A/B-roll 时长统计或占比不正确")
    return {"outlinePath": str(path), "outlineHash": digest(path), "chapterId": str(chapter_id) if chapter_id is not None else None, "stats": expected_overall}, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outline", required=True)
    parser.add_argument("--chapter")
    parser.add_argument("--project-root")
    args = parser.parse_args()
    try:
        evidence, errors = validate(args.outline, args.chapter, args.project_root)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"错误：视觉梗概无法校验：{exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    print(json.dumps(evidence, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
