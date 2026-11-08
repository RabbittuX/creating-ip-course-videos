#!/usr/bin/env python3
"""Validate B-roll candidates, inspection evidence, state progress, and reuse balance."""

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from validate_visual_assembly import structural_fingerprint


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


def validate_state_timeline(label, item, errors):
    if not item.get("stateProgress"):
        return
    timeline = sorted(item.get("stateTimeline", []), key=lambda x: float(x.get("time", 0)))
    if not timeline:
        errors.append(f"{label} 状态模板缺少 stateTimeline")
        return
    previous_progress = -1.0
    previous_completed = set()
    all_items = set()
    for state in timeline:
        active = state.get("active")
        completed = set(state.get("completed", []))
        unvisited = set(state.get("unvisited", []))
        all_items.update(completed | unvisited | ({active} if active else set()))
        progress = float(state.get("progress", 0) or 0)
        if progress < previous_progress or not previous_completed.issubset(completed):
            errors.append(f"{label} 状态发生倒退或回跳：t={state.get('time')}")
        if active and (active in completed or active in unvisited):
            errors.append(f"{label} 当前项同时出现在已完成/未访问状态：{active}")
        previous_progress = progress
        previous_completed = completed
    final = timeline[-1]
    if final.get("active") is not None or final.get("unvisited") or float(final.get("progress", 0) or 0) < 1:
        errors.append(f"{label} 最终状态必须全部完成，并隐藏黄色焦点/指针")
    elif set(final.get("completed", [])) != all_items:
        errors.append(f"{label} 最终状态未保留全部绿色完成项")


def validate_narration_mapping(label, item, errors):
    """Lightweight contract: mapping exists, time increases, shared driver is used."""
    if not item.get("stateProgress"):
        return
    registry = item.get("registryEntry") or {}
    if item.get("stateDriver") != "broll-progress-controller" or registry.get("stateDriver") != "broll-progress-controller":
        errors.append(f"{label} 流程推进必须使用 broll-progress-controller，禁止手写平均时间")
    map_path = item.get("narrationMapPath")
    timeline_path = item.get("resolvedTimelinePath")
    if not map_path or not Path(map_path).is_file():
        errors.append(f"{label} 缺少 B-roll 口播映射文件")
        return
    if not timeline_path or not Path(timeline_path).is_file():
        errors.append(f"{label} 缺少词级对齐后的 B-roll 时间线")
        return
    try:
        mapping = load_json(map_path)
        timeline = load_json(timeline_path)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label} 无法读取口播映射/时间线：{exc}")
        return
    map_ids = [entry.get("itemId") for entry in mapping.get("items", [])]
    timed = timeline.get("items", [])
    timed_ids = [entry.get("itemId") for entry in timed]
    if not map_ids or map_ids != timed_ids:
        errors.append(f"{label} 口播映射项与时间线项不一致")
    previous = -1
    for entry in timed:
        active = entry.get("activeAtMs")
        complete = entry.get("completeAtMs")
        if not isinstance(active, (int, float)) or not isinstance(complete, (int, float)) or active < previous or complete <= active:
            errors.append(f"{label} 时间线不是递增的有效区间：{entry.get('itemId')}")
            break
        previous = active


def validate_inspection(label, item, profile, errors):
    inspection = item.get("inspection") or {}
    frames = inspection.get("sampledFrames") or []
    if not frames:
        if profile.get("inspection", {}).get("required"):
            errors.append(f"{label} 缺少画面检查报告")
        return
    canvas = inspection.get("canvas", {})
    expected = profile["canvas"]
    if canvas.get("width") != expected["width"] or canvas.get("height") != expected["height"]:
        errors.append(f"{label} 检查画布不是 {expected['width']}×{expected['height']}")
    duration = float(item.get("durationSeconds") or item.get("cueWindow", {}).get("end", 0) or 0)
    times = [float(frame.get("time", 0) or 0) for frame in frames]
    if profile["inspection"].get("requireFirstAndLastFrame"):
        if min(times) > 0.1:
            errors.append(f"{label} 缺少首帧检查")
        if duration and max(times) < duration - 0.2:
            errors.append(f"{label} 缺少尾帧检查，无法排除结尾回跳或白闪")
    for frame in frames:
        at = frame.get("time")
        if int(frame.get("textOverflowCount", 0) or 0) > 0:
            errors.append(f"{label} 在 {at}s 检出文字溢出")
        if int(frame.get("outOfBoundsCount", 0) or 0) > 0:
            errors.append(f"{label} 在 {at}s 检出元素越过安全区")
        if int(frame.get("focusMisalignedCount", 0) or 0) > 0:
            errors.append(f"{label} 在 {at}s 检出选中框/焦点错位")
        if frame.get("whiteFrame") is True:
            errors.append(f"{label} 在 {at}s 检出白屏或白闪")
        if item.get("stateProgress"):
            observed = {k: str(v).lower() for k, v in (frame.get("stateColors") or {}).items()}
            for role, expected_color in profile["stateColors"].items():
                if role in observed and observed[role] != expected_color.lower():
                    errors.append(f"{label} 在 {at}s 的 {role} 状态颜色错误：{observed[role]}")
    if item.get("stateProgress"):
        if not any((frame.get("stateColors") or {}).get("active") for frame in frames):
            errors.append(f"{label} 缺少黄色当前状态的独立颜色检查")
        if not any((frame.get("stateColors") or {}).get("completed") for frame in frames):
            errors.append(f"{label} 缺少绿色已完成状态的独立颜色检查")
        if frames[-1].get("focusVisible") is not False:
            errors.append(f"{label} 结尾黄色焦点/指针仍然可见")


def registered_template_instance(item):
    template = item.get("templateSourcePath")
    source = item.get("sourcePath")
    return bool(
        item.get("sourceMode") == "template"
        and item.get("approvalBasis") == "approved-visual-outline-template-selection"
        and template and source and Path(template).is_file() and Path(source).is_file()
        and item.get("templateSourceHash") == sha256(template)
        and structural_fingerprint(template) == structural_fingerprint(source)
    )


def validate_narration(label, item, profile, errors):
    cue = item.get("cueWindow") or {}
    start = float(cue.get("start", 0) or 0)
    end = float(cue.get("end", 0) or 0)
    if not str(item.get("narrationCue", "")).strip() or end <= start:
        errors.append(f"{label} 缺少有效口播 cue 与时间窗口")
    states = {float(x.get("time", 0)): x for x in item.get("stateTimeline", [])}
    for event in item.get("visualEvents", []):
        at = float(event.get("time", 0) or 0)
        if at < start or at > end:
            errors.append(f"{label} 画面步骤与口播时间不同步：{at}s 不在 {start:g}-{end:g}s")
        if states and at in states:
            state = states[at]
            target = event.get("target")
            visible_target = target == state.get("active") or target in set(state.get("completed", []))
            if not visible_target:
                errors.append(f"{label} 画面步骤与口播目标不同步：{target} 与当前状态不一致")
    if not registered_template_instance(item):
        for check in profile["requiredHumanChecks"]:
            if item.get("humanChecks", {}).get(check) != "pass":
                errors.append(f"{label} 口播/语义人工检查未通过：{check}")


def validate_real_ui(label, item, errors):
    if item.get("sourceMode") == "schematic" and item.get("claimRealUi") is True:
        errors.append(f"{label} 示意画面不得标记为真实操作页面")
    if item.get("sourceMode") != "real-ui":
        return
    provenance = item.get("realUi") or {}
    source = provenance.get("originalAssetPath")
    if not source or not Path(source).is_file():
        errors.append(f"{label} 真实截图缺少原始素材溯源")
    elif provenance.get("originalAssetHash") != sha256(source):
        errors.append(f"{label} 真实截图原始素材哈希不一致")
    if not provenance.get("expectedDomain") or provenance.get("expectedDomain") != provenance.get("detectedDomain"):
        errors.append(f"{label} 真实截图域名与预期页面不一致")
    if not provenance.get("expectedPage") or provenance.get("expectedPage") != provenance.get("detectedPage"):
        errors.append(f"{label} 真实截图页面身份无法确认")
    if item.get("humanChecks", {}).get("realUiAuthenticity") != "pass":
        errors.append(f"{label} 真实截图真实性人工检查未通过")


def validate_balance(data, profile, warnings):
    uses = data.get("selectionAudit", {}).get("uses", [])
    family_total = Counter(x.get("family") for x in uses)
    template_total = Counter((x.get("family"), x.get("templateId")) for x in uses)
    threshold = float(profile["selection"]["familyShareWarningThreshold"])
    variant_threshold = int(profile["selection"]["familyVariantThreshold"])
    variants = defaultdict(int)
    last_seen = {}
    minimum_gap = int(profile["selection"]["minFunctionalScenesBetweenExactRepeats"])
    for item in uses:
        variants[item.get("family")] = max(variants[item.get("family")], int(item.get("eligibleFamilyVariants", 0) or 0))
    for index, item in enumerate(uses):
        template_id = item.get("templateId")
        eligible_count = max(
            int(item.get("eligibleFamilyVariants", 0) or 0),
            len(item.get("eligibleTemplateIds", [])),
        )
        if template_id in last_seen and index - last_seen[template_id] - 1 < minimum_gap and eligible_count > 1:
            warnings.append(
                f"{template_id} 两次使用之间不足 {minimum_gap} 个功能 B-roll 场景"
            )
        last_seen[template_id] = index
    for (family, template_id), count in template_total.items():
        total = family_total[family]
        if total and variants[family] >= variant_threshold and count / total > threshold:
            warnings.append(f"{family}/{template_id} 使用占比 {count / total:.0%} 超过 40%")


def validate_manifest(data, profile, mode="review", candidate_ids=None):
    errors, warnings = [], []
    selected = set(candidate_ids or [])
    candidates = [x for x in data.get("candidates", []) if not selected or x.get("candidateId") in selected]
    candidate_root = data.get("candidateRoot")
    approved_root = data.get("approvedRoot")
    if not candidate_root:
        errors.append("缺少 candidateRoot；新 B-roll 必须进入候选隔离区")
    if not approved_root:
        errors.append("缺少 approvedRoot；正式工程只能读取已批准 B-roll")
    if mode == "preview" and not candidates:
        errors.append("B-roll preview 校验要求至少一个已批准候选")
    for item in candidates:
        label = item.get("candidateId") or "<missing-candidate-id>"
        if label == "<missing-candidate-id>":
            errors.append("B-roll 候选缺少 candidateId")
            continue
        source = item.get("sourcePath")
        if not source or not Path(source).is_file():
            errors.append(f"{label} 缺少候选动画源：{source}")
        elif candidate_root and not inside(source, candidate_root):
            errors.append(f"{label} 未位于候选隔离区")
        elif item.get("sourceHash") != sha256(source):
            errors.append(f"{label} 素材哈希与清单不一致")
        for field in ("templateId", "version", "family", "sourceMode"):
            if item.get(field) in (None, ""):
                errors.append(f"{label} 缺少字段：{field}")
        if item.get("sourceMode") not in {"template", "schematic", "real-ui"}:
            errors.append(f"{label} sourceMode 无效：{item.get('sourceMode')}")
        registry_entry = item.get("registryEntry") or {}
        for field in (
            "id", "version", "mode", "family", "minItems", "maxItems",
            "minDurationSeconds", "maxDurationSeconds", "supportedInteractions",
        ):
            if registry_entry.get(field) in (None, ""):
                errors.append(f"{label} registryEntry 缺少字段：{field}")
        if registry_entry.get("id") and registry_entry.get("id") != item.get("templateId"):
            errors.append(f"{label} registryEntry.id 与 templateId 不一致")
        progress_mode = item.get("progressMode")
        registry_progress_mode = registry_entry.get("progressMode")
        if progress_mode not in {"static", "narration-driven"}:
            errors.append(f"{label} 缺少有效 progressMode：static|narration-driven")
        if registry_progress_mode not in {"static", "narration-driven"}:
            errors.append(f"{label} registryEntry 缺少有效 progressMode")
        elif progress_mode != registry_progress_mode:
            errors.append(f"{label} progressMode 与 registryEntry 不一致")
        if progress_mode == "narration-driven" and item.get("stateProgress") is not True:
            errors.append(f"{label} narration-driven B-roll 必须启用 stateProgress")
        if progress_mode == "static" and item.get("stateProgress"):
            errors.append(f"{label} static B-roll 不得伪装成流程推进")
        validate_narration_mapping(label, item, errors)
        validate_inspection(label, item, profile, errors)
        validate_state_timeline(label, item, errors)
        validate_narration(label, item, profile, errors)
        validate_real_ui(label, item, errors)
        if mode == "preview":
            approval = data.get("approvals", {}).get(label)
            approved = item.get("approvedSourcePath")
            registered = registered_template_instance(item)
            if registered and item.get("status") != "READY":
                errors.append(f"{label} 注册模板实例尚未 READY")
            elif not registered and (item.get("status") != "APPROVED" or not approval):
                errors.append(f"{label} 未批准，不能进入 preview")
            elif not registered and approval.get("sourceHash") != item.get("sourceHash"):
                errors.append(f"{label} approved 记录与素材哈希不一致")
            if not approved or not Path(approved).is_file():
                errors.append(f"{label} 缺少 approved 正式动画源")
            elif approved_root and not inside(approved, approved_root):
                errors.append(f"{label} 正式动画源不在 approvedRoot")
            elif sha256(approved) != item.get("sourceHash"):
                errors.append(f"{label} 正式动画源哈希发生变化")
    if selected:
        found = {x.get("candidateId") for x in candidates}
        for missing in sorted(selected - found):
            errors.append(f"不存在的 candidateId：{missing}")
    validate_balance(data, profile, warnings)
    return errors, warnings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--mode", choices=("review", "preview"), default="review")
    parser.add_argument("--candidate-id", action="append")
    args = parser.parse_args()
    errors, warnings = validate_manifest(load_json(args.manifest), load_json(args.profile), args.mode, args.candidate_id)
    for warning in warnings:
        print(f"警告：{warning}")
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    print(f"B-roll {args.mode} 校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
