#!/usr/bin/env python3
"""Manage the sequential human-review workflow for IP course chapters."""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from validate_aroll import load_json as load_aroll_json, validate_manifest as validate_aroll_manifest
from validate_audio_ready import validate as validate_audio_ready
from validate_broll_sync_ready import validate as validate_broll_sync_ready
from validate_environment_cast import validate as validate_environment_cast
from validate_preview_ready import validate as validate_preview_ready
from validate_output_evidence import delivery as validate_delivery_ready, final_qc as validate_final_qc_ready, render as validate_render_ready
from validate_visual_outline import validate as validate_visual_outline
from build_actual_duration_report import write_report as write_actual_duration_report

GATE_REQUIREMENTS = {
    "environment-cast": [],
    "visual-outline": ["ENVIRONMENT_CAST_APPROVED"],
    "aroll-images": ["VISUAL_OUTLINE_APPROVED"],
    "preview": ["PREVIEW_READY"],
}
MILESTONE_REQUIREMENTS = {
    "audio": ["AROLL_IMAGES_APPROVED"],
    "broll-sync": ["AUDIO_READY"],
    "preview-ready": ["BROLL_SYNC_READY"],
    "rendered": ["PREVIEW_APPROVED"],
    "final-qc": ["RENDERED"],
    "delivery": ["FINAL_QC_PASSED"],
}
GLOBAL_GATE_REQUIREMENTS = {
    "environment-cast": [],
    "visual-outline": ["ENVIRONMENT_CAST_APPROVED"],
    "aroll-images": ["VISUAL_OUTLINE_APPROVED"],
    "preview": ["PREVIEW_READY"],
}
GLOBAL_MILESTONE_REQUIREMENTS = {
    "audio": ["AROLL_IMAGES_APPROVED"],
    "broll-sync": [],
    "preview-ready": ["BROLL_SYNC_READY"],
    "rendered": ["PREVIEW_APPROVED"],
    "final-qc": [],
    "delivery": ["FINAL_QC_PASSED"],
}
GATE_TOKENS = {
    "environment-cast": "ENVIRONMENT_CAST_APPROVED",
    "visual-outline": "VISUAL_OUTLINE_APPROVED",
    "aroll-images": "AROLL_IMAGES_APPROVED",
    "preview": "PREVIEW_APPROVED",
}
MILESTONE_TOKENS = {
    "audio": "AUDIO_READY",
    "broll-sync": "BROLL_SYNC_READY",
    "preview-ready": "PREVIEW_READY",
    "rendered": "RENDERED",
    "final-qc": "FINAL_QC_PASSED",
    "delivery": "DELIVERY_READY",
}
ORDER = [
    "ENVIRONMENT_CAST_APPROVED", "VISUAL_OUTLINE_APPROVED", "AROLL_IMAGES_APPROVED",
    "AUDIO_READY", "BROLL_SYNC_READY", "PREVIEW_READY", "PREVIEW_APPROVED",
    "RENDERED", "FINAL_QC_PASSED", "DELIVERY_READY",
]


def now():
    return datetime.now(timezone.utc).isoformat()


def blank_chapter():
    return {
        "state": "NARRATION_INDEXED",
        "milestones": {name: None for name in MILESTONE_REQUIREMENTS},
        "requests": {name: None for name in GATE_REQUIREMENTS},
        "approvals": {name: None for name in GATE_REQUIREMENTS},
        "history": [],
    }


def save(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for item in data.get("chapters", {}).values():
        item.setdefault("milestones", {})
        item.setdefault("requests", {})
        item.setdefault("approvals", {})
        for name in MILESTONE_REQUIREMENTS:
            item["milestones"].setdefault(name, None)
        for name in GATE_REQUIREMENTS:
            item["requests"].setdefault(name, None)
            item["approvals"].setdefault(name, None)
    return data


def get_chapter(data, chapter_id):
    try:
        return data["chapters"][chapter_id]
    except KeyError:
        raise SystemExit(f"未知章节：{chapter_id}")


def available_tokens(item):
    tokens = {MILESTONE_TOKENS[name] for name, evidence in item.get("milestones", {}).items() if name in MILESTONE_TOKENS and evidence}
    tokens.update(GATE_TOKENS[name] for name, evidence in item.get("approvals", {}).items() if name in GATE_TOKENS and evidence)
    return tokens


def missing(item, requirements):
    have = available_tokens(item)
    return [token for token in requirements if token not in have]


def missing_global(data, requirements):
    result = []
    for chapter_id, chapter in data.get("chapters", {}).items():
        for token in missing(chapter, requirements):
            result.append(f"{chapter_id}:{token}")
    return result


def refresh_state(item):
    have = available_tokens(item)
    item["state"] = next((token for token in reversed(ORDER) if token in have), "NARRATION_INDEXED")


def invalidate_from(item, token, reason):
    affected = set(ORDER[ORDER.index(token):])
    for name, gate_token in GATE_TOKENS.items():
        if gate_token in affected:
            item["approvals"][name] = None
            if gate_token != token:
                item["requests"][name] = None
    for name, milestone_token in MILESTONE_TOKENS.items():
        if milestone_token in affected:
            item["milestones"][name] = None
    item["history"].append({"action": "invalidate", "from": token, "reason": reason, "at": now()})


def sync_project_state(root, data):
    root = Path(root).resolve()
    project_path = root / "project.json"
    if not project_path.is_file():
        return
    project = json.loads(project_path.read_text(encoding="utf-8"))
    chapter_index = {str(item.get("id")): item for item in project.get("chapters", [])}
    for chapter_id, evidence in data.get("chapters", {}).items():
        refresh_state(evidence)
        state = evidence["state"]
        if chapter_id in chapter_index:
            chapter_index[chapter_id]["state"] = state
        missing_tokens = [token for token in ORDER if token not in available_tokens(evidence)]
        status_path = root / "chapters" / chapter_id / "chapter-status.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        save(status_path, {"chapterId": chapter_id, "state": state, "missing": missing_tokens})
    save(project_path, project)


def project_root(args):
    return Path(args.project_root).resolve() if getattr(args, "project_root", None) else Path(args.file).resolve().parent


def review_artifact(root, gate, chapter_id, build_id=None):
    if gate == "environment-cast":
        return validate_environment_cast(root, chapter_id)
    if gate == "visual-outline":
        return validate_visual_outline(Path(root) / "planning" / "visual-outline.json", chapter_id)
    if gate == "aroll-images":
        manifest_path = Path(root) / "planning" / "aroll-manifest.json"
        profile_path = Path(__file__).resolve().parent.parent / "assets" / "presets" / "aroll-profile.json"
        evidence = {"manifestPath": str(manifest_path), "chapterId": str(chapter_id)}
        if not manifest_path.is_file():
            return evidence, ["A-roll 清单不存在"]
        data = load_aroll_json(manifest_path)
        errors, _ = validate_aroll_manifest(data, load_aroll_json(profile_path), "review")
        if not data.get("candidates") or not data.get("sequences"):
            errors.append("A-roll 候选图或动作序列为空")
        chapter_sequences = [item for item in data.get("sequences", []) if str(item.get("chapterId")) == str(chapter_id)]
        chapter_sequence_ids = {item.get("id") for item in chapter_sequences}
        chapter_candidates = [item for item in data.get("candidates", []) if item.get("sequenceId") in chapter_sequence_ids]
        outline_path = Path(root) / "planning" / "visual-outline.json"
        expected_scenes = set()
        if outline_path.is_file():
            outline = json.loads(outline_path.read_text(encoding="utf-8"))
            chapter = next((item for item in outline.get("chapters", []) if str(item.get("chapterId", item.get("id", ""))) == str(chapter_id)), None)
            if chapter:
                expected_scenes = {str(item.get("sceneId", item.get("id", ""))) for item in chapter.get("scenes", []) if str(item.get("type", "")).lower().replace("-", "") == "aroll"}
        covered_scenes = {str(item.get("sceneId", "")) for item in chapter_sequences}
        covered_scenes.update(str(beat.get("sceneId", "")) for item in chapter_sequences for beat in item.get("beats", []))
        covered_scenes.discard("")
        if not chapter_sequences or not chapter_candidates:
            errors.append(f"章节 {chapter_id} 缺少自己的 A-roll 动作序列或候选图")
        if expected_scenes - covered_scenes:
            errors.append(f"章节 {chapter_id} A-roll 未覆盖镜头：{', '.join(sorted(expected_scenes - covered_scenes))}")
        evidence.update({"manifestHash": hashlib.sha256(manifest_path.read_bytes()).hexdigest(), "candidateIds": [item.get("candidateId") for item in chapter_candidates], "sceneIds": sorted(covered_scenes)})
        return evidence, [f"A-roll：{error}" for error in errors]
    if gate == "preview":
        return validate_preview_ready(root, chapter_id, build_id)
    return {}, []


def changed_since_request(request, evidence):
    previous = request.get("evidence") or {}
    for key in ("planHash", "registryHash", "narrationManifestHash", "outlineHash", "manifestHash", "timelineHash", "previewManifestHash", "creativeDirectivesHash", "brollManifestHash", "brollLockHash"):
        if key in previous and previous.get(key) != evidence.get(key):
            return True
    return False


def promote_planning_artifact(root, gate):
    names = {"environment-cast": "environment-cast-plan.json", "visual-outline": "visual-outline.json"}
    name = names.get(gate)
    if not name:
        return
    path = Path(root) / "planning" / name
    data = json.loads(path.read_text(encoding="utf-8"))
    data["status"] = "APPROVED"
    save(path, data)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--file", required=True)
    init.add_argument("--chapters", required=True)
    ready = sub.add_parser("mark-ready")
    ready.add_argument("--file", required=True)
    ready.add_argument("--chapter", required=True)
    ready.add_argument("--milestone", choices=MILESTONE_REQUIREMENTS, required=True)
    ready.add_argument("--build-id", required=True)
    ready.add_argument("--project-root")
    for command in ("request", "approve"):
        action = sub.add_parser(command)
        action.add_argument("--file", required=True)
        action.add_argument("--chapter", required=True)
        action.add_argument("--gate", choices=GATE_REQUIREMENTS, required=True)
        action.add_argument("--build-id", required=True)
        action.add_argument("--project-root")
        if command == "approve":
            action.add_argument("--approved-by", required=True)
    invalid = sub.add_parser("invalidate")
    invalid.add_argument("--file", required=True)
    invalid.add_argument("--chapter", required=True)
    invalid.add_argument("--from", dest="from_token", choices=ORDER, required=True)
    invalid.add_argument("--reason", required=True)
    args = parser.parse_args()

    if args.command == "init":
        ids = [value.strip() for value in args.chapters.split(",") if value.strip()]
        save(args.file, {"schemaVersion": 3, "chapters": {chapter_id: blank_chapter() for chapter_id in ids}})
        return 0

    data = load(args.file)
    item = get_chapter(data, args.chapter)
    if args.command == "mark-ready":
        unmet = missing(item, MILESTONE_REQUIREMENTS[args.milestone])
        if unmet:
            print(f"不能标记 {MILESTONE_TOKENS[args.milestone]}，缺少：{', '.join(unmet)}", file=sys.stderr)
            return 2
        unmet_global = missing_global(data, GLOBAL_MILESTONE_REQUIREMENTS[args.milestone])
        if unmet_global:
            print(f"不能标记 {MILESTONE_TOKENS[args.milestone]}，全片尚有章节未完成上一阶段：{', '.join(unmet_global)}", file=sys.stderr)
            return 2
        evidence = None
        if args.milestone == "audio":
            if not args.project_root:
                print("不能标记 AUDIO_READY：必须提供 --project-root 检查音频与词级对齐证据", file=sys.stderr)
                return 2
            evidence, artifact_errors = validate_audio_ready(args.project_root, args.chapter)
            if artifact_errors:
                for error in artifact_errors:
                    print(f"不能标记 AUDIO_READY：{error}", file=sys.stderr)
                return 2
            report_path, report, duration_errors = write_actual_duration_report(args.project_root, args.chapter)
            if duration_errors:
                for chapter in data.get("chapters", {}).values():
                    invalidate_from(chapter, "VISUAL_OUTLINE_APPROVED", "实际口播时长与批准视觉梗概偏差超限")
                save(args.file, data)
                sync_project_state(project_root(args), data)
                for error in duration_errors:
                    print(f"不能标记 AUDIO_READY：{error}", file=sys.stderr)
                return 2
            evidence.update({"actualDurationReportPath": str(report_path), "actualDurationStatus": report.get("status"), "actualDurationReportHash": hashlib.sha256(report_path.read_bytes()).hexdigest()})
        elif args.milestone == "broll-sync":
            if not args.project_root:
                print("不能标记 BROLL_SYNC_READY：必须提供 --project-root 检查口播映射、时间线和运行时接线", file=sys.stderr)
                return 2
            evidence, artifact_errors = validate_broll_sync_ready(args.project_root, args.chapter)
            if artifact_errors:
                for error in artifact_errors:
                    print(f"不能标记 BROLL_SYNC_READY：{error}", file=sys.stderr)
                return 2
        elif args.milestone == "preview-ready":
            if not args.project_root:
                print("不能标记 PREVIEW_READY：必须提供 --project-root 检查完整父时间线", file=sys.stderr)
                return 2
            evidence, artifact_errors = validate_preview_ready(args.project_root, args.chapter, args.build_id)
            if artifact_errors:
                for error in artifact_errors:
                    print(f"不能标记 PREVIEW_READY：{error}", file=sys.stderr)
                return 2
        elif args.milestone in {"rendered", "final-qc", "delivery"}:
            if not args.project_root:
                print(f"不能标记 {MILESTONE_TOKENS[args.milestone]}：必须提供 --project-root 检查产物证据", file=sys.stderr)
                return 2
            validators = {"rendered": validate_render_ready, "final-qc": validate_final_qc_ready, "delivery": validate_delivery_ready}
            validator = validators[args.milestone]
            evidence, artifact_errors = validator(args.project_root, args.chapter, args.build_id) if args.milestone == "rendered" else validator(args.project_root, args.chapter)
            if artifact_errors:
                for error in artifact_errors:
                    print(f"不能标记 {MILESTONE_TOKENS[args.milestone]}：{error}", file=sys.stderr)
                return 2
        item["milestones"][args.milestone] = {"buildId": args.build_id, "readyAt": now(), "evidence": evidence}
        item["history"].append({"action": "mark-ready", "milestone": args.milestone, "buildId": args.build_id, "at": now()})
    elif args.command == "request":
        unmet = missing(item, GATE_REQUIREMENTS[args.gate])
        if unmet:
            print(f"不能进入 {args.gate} 审核，缺少：{', '.join(unmet)}", file=sys.stderr)
            return 2
        unmet_global = missing_global(data, GLOBAL_GATE_REQUIREMENTS[args.gate])
        if unmet_global:
            print(f"不能进入 {args.gate} 审核，必须先完成全部章节的全片阶段：{', '.join(unmet_global)}", file=sys.stderr)
            return 2
        evidence, artifact_errors = review_artifact(project_root(args), args.gate, args.chapter, args.build_id)
        if artifact_errors:
            for error in artifact_errors:
                print(f"不能进入 {args.gate} 审核：{error}", file=sys.stderr)
            return 2
        targets = data.get("chapters", {}).values() if args.gate == "preview" else [item]
        for target in targets:
            target["requests"][args.gate] = {"buildId": args.build_id, "requestedAt": now(), "evidence": evidence}
            target["approvals"][args.gate] = None
            target["history"].append({"action": "request", "gate": args.gate, "buildId": args.build_id, "at": now()})
    elif args.command == "approve":
        request = item["requests"].get(args.gate)
        if not request or request.get("buildId") != args.build_id:
            print("批准的 build ID 与待审版本不一致", file=sys.stderr)
            return 2
        evidence, artifact_errors = review_artifact(project_root(args), args.gate, args.chapter, args.build_id)
        if artifact_errors:
            for error in artifact_errors:
                print(f"不能批准 {args.gate}：{error}", file=sys.stderr)
            return 2
        if changed_since_request(request, evidence):
            print("待审产物哈希已经变化，必须重新发起审核", file=sys.stderr)
            return 2
        promote_planning_artifact(project_root(args), args.gate)
        if args.gate in {"environment-cast", "visual-outline"}:
            evidence, artifact_errors = review_artifact(project_root(args), args.gate, args.chapter, args.build_id)
            if artifact_errors:
                for error in artifact_errors:
                    print(f"不能批准 {args.gate}：{error}", file=sys.stderr)
                return 2
        targets = data.get("chapters", {}).values() if args.gate == "preview" else [item]
        for target in targets:
            target["approvals"][args.gate] = {"buildId": args.build_id, "approvedBy": args.approved_by, "approvedAt": now(), "evidence": evidence}
            target["history"].append({"action": "approve", "gate": args.gate, "buildId": args.build_id, "by": args.approved_by, "at": now()})
    else:
        for chapter in data.get("chapters", {}).values():
            invalidate_from(chapter, args.from_token, args.reason)
    refresh_state(item)
    data["schemaVersion"] = 3
    save(args.file, data)
    sync_project_state(project_root(args), data)
    print(f"章节 {args.chapter} 当前状态：{item['state']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
