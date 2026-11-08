#!/usr/bin/env python3
"""Validate the reviewed chapter background/cast plan against canonical assets."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from narration_contract import validate_manifest as validate_narration_manifest


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve(root, value):
    path = Path(value)
    return path if path.is_absolute() else root / path


def validate(project_root, chapter_id):
    root = Path(project_root).resolve()
    manifest_path = root / "project.json"
    plan_path = root / "planning" / "environment-cast-plan.json"
    evidence = {"planPath": str(plan_path), "chapterId": str(chapter_id)}
    errors = []
    if not manifest_path.is_file() or not plan_path.is_file():
        return evidence, ["缺少 project.json 或背景与人物方案 environment-cast-plan.json"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    narration_evidence, narration_errors = validate_narration_manifest(root, chapter_id)
    errors.extend(narration_errors)
    if plan.get("status") not in {"REVIEW_READY", "APPROVED"}:
        errors.append("背景与人物方案必须标记为 REVIEW_READY")
    chapter = next((item for item in plan.get("chapters", []) if str(item.get("chapterId", item.get("id", ""))) == str(chapter_id)), None)
    if not chapter:
        return evidence, errors + [f"背景与人物方案缺少章节 {chapter_id}"]
    narration = chapter.get("narrationRange") or {}
    source = str(narration.get("sourceText", ""))
    start, end = narration.get("sourceCharStart"), narration.get("sourceCharEnd")
    if not source or not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start or end - start != len(source):
        errors.append("章节背景方案缺少有效的真实口播范围")
    elif not narration_errors and (start != 0 or end != len(narration_evidence["canonicalNarration"]) or source != narration_evidence["canonicalNarration"]):
        errors.append("章节背景方案口播范围必须完整匹配唯一主口播")
    background = chapter.get("background") or {}
    for field in ("backgroundId", "label", "reason"):
        if not str(background.get(field, "")).strip():
            errors.append(f"章节背景缺少字段：{field}")
    if not isinstance(background.get("sharedWith", []), list):
        errors.append("background.sharedWith 必须是章节 ID 数组")
    action_chain = chapter.get("actionChain") or []
    if not isinstance(action_chain, list) or not action_chain or any(not str(item).strip() for item in action_chain):
        errors.append("章节必须包含连续动作链 actionChain")
    scene_bible = chapter.get("sceneBible") or {}
    for field, label in (("environmentDescription", "场景背景"), ("screenBackground", "屏幕背景"), ("cameraFraming", "镜头位置"), ("continuityNotes", "连续性说明")):
        if not str(scene_bible.get(field, "")).strip():
            errors.append(f"场景圣经 sceneBible 缺少{label}：{field}")
    actor_positions = scene_bible.get("actorPositions")
    if not isinstance(actor_positions, list) or not actor_positions or any(not str(item).strip() for item in actor_positions):
        errors.append("场景圣经 sceneBible 缺少人物位置 actorPositions")

    registry_value = manifest.get("characterRegistry")
    if not registry_value:
        return evidence, errors + ["project.json 缺少 characterRegistry"]
    registry_path = resolve(root, registry_value).resolve()
    if not registry_path.is_file():
        return evidence, errors + [f"角色定稿注册表不存在：{registry_path}"]
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    canonical = {item.get("characterId"): item for item in registry.get("characters", [])}
    cast = chapter.get("cast") or []
    if not cast:
        errors.append("章节参演人物 cast 不能为空")
    cast_ids = []
    for item in cast:
        cid = item.get("characterId")
        cast_ids.append(cid)
        registered = canonical.get(cid)
        if not registered:
            errors.append(f"未注册的参演角色：{cid}")
            continue
        if registered.get("status") != "approved":
            errors.append(f"参演角色尚未定稿：{cid}")
            continue
        if item.get("version") != registered.get("version") or item.get("referenceHash") != registered.get("sha256"):
            errors.append(f"参演角色版本或参考图哈希不匹配：{cid}")
    presence = chapter.get("hostPresence", "required")
    host_ids = {item.get("characterId") for item in registry.get("characters", []) if item.get("role") == "required-host"} or {"ip-host"}
    if presence == "required" and not host_ids & set(cast_ids):
        errors.append("IP 人物为必选但未加入 cast")
    elif presence == "waived" and not str(chapter.get("hostWaiverReason", "")).strip():
        errors.append("不使用 IP 人物时必须说明 hostWaiverReason")
    elif presence not in {"required", "waived"}:
        errors.append("hostPresence 必须为 required 或 waived")
    evidence.update({"planHash": digest(plan_path), "registryPath": str(registry_path), "registryHash": digest(registry_path), "backgroundId": background.get("backgroundId"), "castIds": cast_ids, **narration_evidence})
    return evidence, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--chapter", required=True)
    args = parser.parse_args()
    try:
        evidence, errors = validate(args.project_root, args.chapter)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"错误：背景与人物方案无法校验：{exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    print(json.dumps(evidence, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
