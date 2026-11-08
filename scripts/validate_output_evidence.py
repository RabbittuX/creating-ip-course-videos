#!/usr/bin/env python3
"""Validate low-cost hash evidence for render, QC, and delivery milestones."""

import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def resolve(base, value):
    path = Path(value)
    return path if path.is_absolute() else base / path


def checked_file(base, data, path_key, hash_key, label, errors, evidence):
    value = data.get(path_key)
    target = resolve(base, value).resolve() if value else None
    if not target or not target.is_file():
        errors.append(f"{label}不存在")
        return None
    current = digest(target)
    if data.get(hash_key) != current:
        errors.append(f"{label} {hash_key} 与当前文件哈希不匹配")
    evidence[hash_key] = current
    evidence[path_key] = str(target)
    return target


def render(project_root, chapter_id, build_id=None):
    root = Path(project_root).resolve()
    manifest = root / "renders" / str(chapter_id) / "render-ready.json"
    evidence = {"manifestPath": str(manifest), "chapterId": str(chapter_id)}
    if not manifest.is_file():
        return evidence, ["缺少渲染证据 render-ready.json"]
    data, errors = load(manifest), []
    if data.get("status") != "READY": errors.append("渲染证据状态必须为 READY")
    if str(data.get("chapterId")) != str(chapter_id): errors.append("渲染证据 chapterId 不匹配")
    if build_id and data.get("buildId") != build_id: errors.append("渲染证据 buildId 不匹配")
    approvals = load(root / "approvals.json")
    preview = approvals["chapters"][str(chapter_id)]["approvals"].get("preview") or {}
    if data.get("previewBuildId") != preview.get("buildId"): errors.append("渲染并非来自已批准的 preview build")
    preview_evidence = preview.get("evidence") or {}
    preview_manifest = root / "preview" / "preview-ready.json"
    if not preview_manifest.is_file() or preview_evidence.get("previewManifestHash") != digest(preview_manifest): errors.append("已批准的预览组合证据已变化")
    video = checked_file(manifest.parent, data, "videoPath", "videoHash", "渲染视频", errors, evidence)
    timeline = checked_file(manifest.parent, data, "fullTimelinePath", "fullTimelineHash", "完整父时间线", errors, evidence)
    project_timeline = root / "timing" / "full-timeline.json"
    if timeline and project_timeline.is_file() and digest(timeline) != digest(project_timeline): errors.append("渲染使用的父时间线不是当前版本")
    if timeline and preview_evidence.get("timelineHash") != digest(timeline): errors.append("渲染使用的父时间线不是预览批准版本")
    evidence.update({"manifestHash": digest(manifest), "previewBuildId": data.get("previewBuildId")})
    return evidence, errors


def final_qc(project_root, chapter_id):
    root = Path(project_root).resolve()
    base = root / "renders" / str(chapter_id)
    manifest, render_manifest = base / "final-qc.json", base / "render-ready.json"
    evidence = {"manifestPath": str(manifest), "chapterId": str(chapter_id)}
    if not manifest.is_file() or not render_manifest.is_file(): return evidence, ["缺少 final-qc.json 或 render-ready.json"]
    data, rendered, errors = load(manifest), load(render_manifest), []
    if data.get("status") != "PASSED": errors.append("最终 QC 状态必须为 PASSED")
    if data.get("renderHash") != rendered.get("videoHash"): errors.append("QC 对应的 renderHash 不是当前渲染")
    report_path = checked_file(manifest.parent, data, "reportPath", "reportHash", "QC 报告", errors, evidence)
    if report_path:
        report = load(report_path)
        if report.get("status") != "PASSED" or report.get("videoHash") != rendered.get("videoHash"):
            errors.append("QC 报告未通过或不属于当前渲染")
    required = ("mediaProbe", "captions", "timeline", "approvedAssets", "privacyScan")
    if any(data.get("checks", {}).get(key) is not True for key in required): errors.append("QC 检查项未全部通过")
    evidence.update({"manifestHash": digest(manifest), "renderHash": data.get("renderHash")})
    return evidence, errors


def delivery(project_root, chapter_id):
    root = Path(project_root).resolve()
    manifest = root / "renders" / "final" / "delivery-ready.json"
    evidence = {"manifestPath": str(manifest), "chapterId": str(chapter_id)}
    if not manifest.is_file():
        return evidence, ["缺少全片聚合交付证据 renders/final/delivery-ready.json"]
    data, errors = load(manifest), []
    if data.get("status") != "READY": errors.append("全片交付证据状态必须为 READY")
    project = load(root / "project.json")
    expected = [str(item.get("id")) for item in project.get("chapters", [])]
    entries = data.get("chapters") or []
    actual = [str(item.get("chapterId")) for item in entries]
    if actual != expected:
        errors.append(f"全片交付清单必须按顺序覆盖全部章节：期望 {expected}，实际 {actual}")
    for item in entries:
        cid = str(item.get("chapterId"))
        render_manifest = checked_file(manifest.parent, item, "renderManifestPath", "renderManifestHash", f"章节 {cid} 渲染清单", errors, evidence)
        qc_manifest = checked_file(manifest.parent, item, "qcManifestPath", "qcManifestHash", f"章节 {cid} QC 清单", errors, evidence)
        if render_manifest and str(load(render_manifest).get("chapterId")) != cid:
            errors.append(f"章节 {cid} 渲染清单 chapterId 不匹配")
        if qc_manifest:
            qc = load(qc_manifest)
            if str(qc.get("chapterId")) != cid or qc.get("status") != "PASSED":
                errors.append(f"章节 {cid} QC 清单未通过或 chapterId 不匹配")
    checked_file(manifest.parent, data, "masterPath", "masterHash", "全片母版", errors, evidence)
    checked_file(manifest.parent, data, "uploadPath", "uploadHash", "全片上传版", errors, evidence)
    timeline = checked_file(manifest.parent, data, "fullTimelinePath", "fullTimelineHash", "完整父时间线", errors, evidence)
    project_timeline = root / "timing" / "full-timeline.json"
    if timeline and (not project_timeline.is_file() or digest(timeline) != digest(project_timeline)):
        errors.append("全片交付使用的父时间线不是当前版本")
    loudness_path = checked_file(manifest.parent, data, "loudnessReportPath", "loudnessReportHash", "全片响度报告", errors, evidence)
    if loudness_path:
        loudness = load(loudness_path)
        integrated = loudness.get("integratedLufs")
        loudness_range = loudness.get("loudnessRangeLu")
        peak = loudness.get("truePeakDbtp")
        from user_config import audio_profile as _audio_profile
        audio_profile = _audio_profile()["loudness"]
        if loudness.get("status") != "PASSED" or not isinstance(integrated, (int, float)) or abs(integrated - float(audio_profile["integratedLufs"])) > float(audio_profile["integratedToleranceLu"]) or not isinstance(loudness_range, (int, float)) or abs(loudness_range - float(audio_profile["loudnessRangeLu"])) > float(audio_profile["loudnessRangeToleranceLu"]) or not isinstance(peak, (int, float)) or peak > float(audio_profile["truePeakCeilingDbtp"]):
            errors.append("全片响度报告不满足配置的 LUFS、LRA 或 True Peak 目标值（config.json loudness / audio-profile.json）")
    evidence.update({"manifestHash": digest(manifest), "chapterIds": actual, "buildId": data.get("buildId")})
    return evidence, errors
