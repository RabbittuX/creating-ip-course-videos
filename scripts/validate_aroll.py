#!/usr/bin/env python3
"""Validate quarantined or approved A-roll candidates and action chains."""

import argparse
import hashlib
import json
import sys
from pathlib import Path


BEAT_FIELDS = (
    "id",
    "role",
    "candidateId",
    "narrationCue",
    "actorAction",
    "gazeTarget",
    "propState",
    "durationSeconds",
)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def validate_plan_links(data, errors):
    plan_value = data.get("environmentCastPlan")
    registry_value = data.get("characterRegistry")
    if not plan_value and not registry_value:
        return
    if not plan_value or not registry_value or not Path(plan_value).is_file() or not Path(registry_value).is_file():
        errors.append("A-roll 清单缺少有效的 environmentCastPlan/characterRegistry")
        return
    plan = load_json(plan_value)
    registry = load_json(registry_value)
    if plan.get("status") != "APPROVED":
        errors.append("A-roll 生成前背景与人物方案必须为 APPROVED")
    planned = {str(item.get("chapterId", item.get("id", ""))): item for item in plan.get("chapters", [])}
    canonical = {item.get("characterId"): item for item in registry.get("characters", [])}
    for sequence in data.get("sequences", []):
        sid = sequence.get("id") or "<missing-sequence-id>"
        cid = str(sequence.get("chapterId", ""))
        chapter = planned.get(cid)
        if not chapter:
            errors.append(f"动作序列 {sid} 未关联已批准章节背景")
            continue
        expected_background = (chapter.get("background") or {}).get("backgroundId")
        if sequence.get("backgroundId") != expected_background:
            errors.append(f"动作序列 {sid} 的 backgroundId 与批准背景 {expected_background} 不一致")
        planned_cast = {item.get("characterId"): item for item in chapter.get("cast", [])}
        references = {item.get("characterId"): item for item in sequence.get("castReferences", [])}
        if set(references) != set(planned_cast):
            errors.append(f"动作序列 {sid} 的 castReferences 与批准参演人物不一致")
            continue
        for character_id, approved in planned_cast.items():
            reference = references[character_id]
            registered = canonical.get(character_id) or {}
            if registered.get("status") != "approved":
                errors.append(f"动作序列 {sid} 使用了未定稿角色：{character_id}")
            if reference.get("version") != approved.get("version") or reference.get("referenceHash") != approved.get("referenceHash"):
                errors.append(f"动作序列 {sid} 的角色参考与批准方案不一致：{character_id}")
            if reference.get("version") != registered.get("version") or reference.get("referenceHash") != registered.get("sha256"):
                errors.append(f"动作序列 {sid} 的角色参考不是当前定稿：{character_id}")


def validate_manifest(data, profile, mode="review", candidate_ids=None):
    errors = []
    warnings = []
    hard_max = float(profile["cadence"]["hardMaxStillSeconds"])
    soft_max = float(profile["cadence"]["softMaxStillSeconds"])
    candidate_root = data.get("candidateRoot")
    approved_root = data.get("approvedRoot")
    selected = set(candidate_ids or [])
    candidates = {
        item.get("candidateId"): item
        for item in data.get("candidates", [])
        if not selected or item.get("candidateId") in selected
    }
    validate_plan_links(data, errors)

    if mode == "preview" and not candidates:
        errors.append("A-roll preview 校验要求至少一个已批准候选图")
    if mode == "preview" and not data.get("sequences"):
        errors.append("A-roll preview 校验要求至少一个动作序列")

    if not candidate_root:
        errors.append("缺少 candidateRoot；生成图必须先进入候选隔离区")
    if not approved_root:
        errors.append("缺少 approvedRoot；正式工程只能读取已批准素材")

    for candidate_id, item in candidates.items():
        label = candidate_id or "<missing-candidate-id>"
        if not candidate_id:
            errors.append("候选图缺少 candidateId")
            continue
        asset_path = item.get("assetPath")
        if not asset_path or not Path(asset_path).is_file():
            errors.append(f"{label} 缺少候选完整画面：{asset_path}")
        elif candidate_root and not inside(asset_path, candidate_root):
            errors.append(f"{label} 未位于候选隔离区：{asset_path}")
        elif item.get("assetHash") != sha256(asset_path):
            errors.append(f"{label} 的素材哈希与清单不一致")

        # Identity, anatomy, style, and continuity are deliberately reviewed by
        # the user. Automated validation stays deterministic and structural.

        duration = float(item.get("durationSeconds", 0) or 0)
        if duration <= 0:
            errors.append(f"{label} 时长无效：{duration}")
        elif duration > hard_max:
            errors.append(f"{label} 时长 {duration:g}s 超过单张 A-roll 最长 {hard_max:g}s")
        elif duration > soft_max:
            warnings.append(f"{label} 时长 {duration:g}s 超过建议上限 {soft_max:g}s")

        for field in ("sequenceId", "beatId", "narrationCue", "actorAction", "gazeTarget", "propState"):
            if not str(item.get(field, "")).strip():
                errors.append(f"{label} 缺少字段：{field}")

        if mode == "preview":
            approval = data.get("approvals", {}).get(candidate_id)
            approved_asset = item.get("approvedAssetPath")
            if item.get("status") != "APPROVED" or not approval:
                errors.append(f"{label} 未批准，不能进入 preview")
            elif approval.get("assetHash") != item.get("assetHash"):
                errors.append(f"{label} 的 approved 记录与素材哈希不一致")
            if not approved_asset or not Path(approved_asset).is_file():
                errors.append(f"{label} 缺少 approved 正式素材")
            elif approved_root and not inside(approved_asset, approved_root):
                errors.append(f"{label} 的正式素材不在 approvedRoot")
            elif sha256(approved_asset) != item.get("assetHash"):
                errors.append(f"{label} 的正式素材哈希发生变化")

    all_candidates = {item.get("candidateId"): item for item in data.get("candidates", [])}
    for sequence in data.get("sequences", []):
        sequence_id = sequence.get("id") or "<missing-sequence-id>"
        if not str(sequence.get("worldLockId", "")).strip():
            errors.append(f"动作序列 {sequence_id} 缺少 worldLockId")
        beats = sequence.get("beats", [])
        if not beats:
            errors.append(f"动作序列 {sequence_id} 没有动作节点")
            continue
        previous_id = None
        for index, beat in enumerate(beats):
            beat_id = beat.get("id") or f"#{index + 1}"
            for field in BEAT_FIELDS:
                value = beat.get(field)
                if value is None or (isinstance(value, str) and not value.strip()):
                    errors.append(f"动作节点 {sequence_id}/{beat_id} 缺少字段：{field}")
            if index and beat.get("inheritsFrom") != previous_id:
                errors.append(
                    f"动作节点 {sequence_id}/{beat_id} 必须 inheritsFrom={previous_id}"
                )
            previous_id = beat.get("id")
            candidate = all_candidates.get(beat.get("candidateId"))
            if not candidate:
                errors.append(f"动作节点 {sequence_id}/{beat_id} 引用了不存在的 candidateId")
            elif candidate.get("sequenceId") != sequence.get("id") or candidate.get("beatId") != beat.get("id"):
                errors.append(f"动作节点 {sequence_id}/{beat_id} 与候选图映射不一致")
            elif abs(float(beat.get("durationSeconds", 0) or 0) - float(candidate.get("durationSeconds", 0) or 0)) > 0.001:
                errors.append(f"动作节点 {sequence_id}/{beat_id} 与候选图时长不一致")

    if selected and selected - set(candidates):
        for missing in sorted(selected - set(candidates)):
            errors.append(f"不存在的 candidateId：{missing}")
    return errors, warnings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--mode", choices=("review", "preview"), default="review")
    parser.add_argument("--candidate-id", action="append")
    args = parser.parse_args()
    data = load_json(args.manifest)
    profile = load_json(args.profile)
    errors, warnings = validate_manifest(data, profile, args.mode, args.candidate_id)
    for warning in warnings:
        print(f"警告：{warning}")
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    print(f"A-roll {args.mode} 校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
