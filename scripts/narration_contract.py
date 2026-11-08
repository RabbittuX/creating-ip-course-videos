#!/usr/bin/env python3
"""Canonical per-chapter narration contract shared by every production stage."""

import hashlib
import json
from pathlib import Path


def text_digest(text):
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def validate_manifest(project_root, chapter_id=None):
    root = Path(project_root).resolve()
    path = root / "planning" / "narration-manifest.json"
    errors = []
    if not path.is_file():
        return {}, ["缺少唯一口播清单 planning/narration-manifest.json"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"唯一口播清单无法读取：{exc}"]
    project_path = root / "project.json"
    expected = []
    if project_path.is_file():
        project = json.loads(project_path.read_text(encoding="utf-8"))
        expected = [str(item.get("id")) for item in project.get("chapters", [])]
    entries = data.get("chapters") or []
    ids = [str(item.get("chapterId", "")) for item in entries]
    if len(ids) != len(set(ids)):
        errors.append("唯一口播清单包含重复章节")
    if expected and ids != expected:
        errors.append(f"唯一口播清单章节必须与 project.json 完全一致：期望 {expected}，实际 {ids}")
    by_id = {str(item.get("chapterId", "")): item for item in entries}
    selected = expected if chapter_id is None else [str(chapter_id)]
    for cid in selected:
        item = by_id.get(cid)
        if not item:
            errors.append(f"唯一口播清单缺少章节 {cid}")
            continue
        text = str(item.get("narration", ""))
        if not text.strip():
            errors.append(f"章节 {cid} 主口播为空")
        elif item.get("narrationHash") != text_digest(text):
            errors.append(f"章节 {cid} 主口播 narrationHash 不匹配")
    if data.get("status") != "READY":
        errors.append("唯一口播清单尚未标记为 READY")
    evidence = {
        "narrationManifestPath": str(path),
        "narrationManifestHash": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    if chapter_id is not None and str(chapter_id) in by_id:
        item = by_id[str(chapter_id)]
        evidence.update({"canonicalNarration": str(item.get("narration", "")), "canonicalNarrationHash": item.get("narrationHash")})
    return evidence, errors

