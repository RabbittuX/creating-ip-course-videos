#!/usr/bin/env python3
"""Lightweight artifact validation before BROLL_SYNC_READY."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from prepare_broll_sync import chapter_id, is_broll, validate_scene
from validate_audio_ready import validate as validate_audio_ready
from validate_broll import load_json as load_broll_json, validate_manifest as validate_broll_manifest


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate(project_root, requested_chapter):
    root = Path(project_root).resolve()
    outline_path = root / "planning" / "visual-outline.json"
    errors = []
    evidence = {"outlinePath": str(outline_path), "artifacts": []}
    if not outline_path.is_file():
        return evidence, ["缺少 visual-outline.json，无法验证 B-roll 设计"]
    try:
        outline = load(outline_path)
    except (OSError, json.JSONDecodeError) as exc:
        return evidence, [f"无法读取 visual-outline：{exc}"]
    chapter = next((item for item in outline.get("chapters", []) if chapter_id(item) == str(requested_chapter)), None)
    if not chapter:
        return evidence, [f"visual-outline 缺少章节 {requested_chapter}"]
    scenes = [scene for scene in chapter.get("scenes", []) if is_broll(scene)]
    for scene in scenes:
        scene_id = str(scene.get("sceneId", scene.get("id", "")))
        errors.extend(validate_scene(scene, f"章节 {requested_chapter} / B-roll {scene_id or '<missing-scene-id>'}"))
    manifest_path = root / "planning" / "broll-manifest.json"
    profile_path = Path(__file__).resolve().parent.parent / "assets" / "presets" / "broll-profile.json"
    chapter_candidates = []
    if scenes:
        if not manifest_path.is_file():
            errors.append("缺少 B-roll 正式清单 planning/broll-manifest.json")
        else:
            manifest = load_broll_json(manifest_path)
            chapter_candidates = [item for item in manifest.get("candidates", []) if str(item.get("chapterId")) == str(requested_chapter)]
            by_scene = {str(item.get("sceneId", "")): item for item in chapter_candidates}
            expected_scene_ids = {str(item.get("sceneId", item.get("id", ""))) for item in scenes}
            missing_scenes = expected_scene_ids - set(by_scene)
            if missing_scenes:
                errors.append(f"章节 {requested_chapter} B-roll 正式清单未覆盖：{', '.join(sorted(missing_scenes))}")
            candidate_ids = [item.get("candidateId") for item in chapter_candidates if item.get("candidateId")]
            manifest_errors, _ = validate_broll_manifest(manifest, load_broll_json(profile_path), "preview", candidate_ids)
            errors.extend(f"B-roll 正式素材：{error}" for error in manifest_errors)
            for scene in scenes:
                sid = str(scene.get("sceneId", scene.get("id", "")))
                composition_value = scene.get("compositionPath")
                composition = Path(composition_value) if composition_value else None
                if composition and not composition.is_absolute():
                    composition = root / composition
                if not composition or not composition.is_file():
                    errors.append(f"B-roll {sid} 缺少实际组合文件 compositionPath")
                    continue
                expected_hash = scene.get("compositionHash")
                if not expected_hash or digest(composition) != expected_hash:
                    errors.append(f"B-roll {sid} compositionHash 缺失或与当前组合文件不匹配")
                candidate = by_scene.get(sid)
                if candidate and candidate.get("approvedSourcePath") and Path(candidate["approvedSourcePath"]).resolve() != composition.resolve():
                    errors.append(f"B-roll {sid} 实际组合文件不是已批准正式素材")
            evidence.update({"brollManifestPath": str(manifest_path), "brollManifestHash": digest(manifest_path)})
        template_scenes = [scene for scene in scenes if scene.get("designOrigin") == "template"]
        if template_scenes:
            lock_path = root / "locks" / "broll-selection.json"
            if not lock_path.is_file():
                errors.append("模板 B-roll 缺少 locks/broll-selection.json")
            else:
                lock = load(lock_path)
                selected = {(str(item.get("chapterId")), str(item.get("sceneId"))): item for item in lock.get("selections", [])}
                for scene in template_scenes:
                    sid = str(scene.get("sceneId", scene.get("id", "")))
                    choice = selected.get((str(requested_chapter), sid))
                    if not choice or choice.get("templateId") != scene.get("templateId"):
                        errors.append(f"模板 B-roll {sid} 与选择锁不一致")
                evidence.update({"brollLockPath": str(lock_path), "brollLockHash": digest(lock_path)})
    driven = [scene for scene in scenes if scene.get("progressMode") == "narration-driven"]
    if not driven:
        evidence["outlineHash"] = digest(outline_path)
        return evidence, errors
    map_path = root / "chapters" / str(requested_chapter) / "planning" / "broll-narration-map.json"
    timeline_path = root / "chapters" / str(requested_chapter) / "timing" / "broll-state-timeline.json"
    if not map_path.is_file() or not timeline_path.is_file():
        errors.append("缺少 B-roll 口播映射或词级时间线")
        return evidence, errors
    try:
        mapping, timeline = load(map_path), load(timeline_path)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"无法读取 B-roll 口播映射/时间线：{exc}")
        return evidence, errors
    audio_evidence, audio_errors = validate_audio_ready(root, requested_chapter)
    errors.extend(f"音频证据：{error}" for error in audio_errors)
    if not audio_errors:
        if timeline.get("alignmentHash") != audio_evidence.get("alignmentHash"):
            errors.append("B-roll 时间线不是由当前词级对齐生成")
        if timeline.get("sourceAudioHash") != audio_evidence.get("audioHash"):
            errors.append("B-roll 时间线对应的音频已经变化，必须重新解析")
        alignment = load(audio_evidence["alignmentPath"])
        if str(mapping.get("narration", "")).strip() != str(alignment.get("narration", "")).strip():
            errors.append("B-roll 口播映射与当前音频对齐文本不一致")
    map_keys = [(str(item.get("sceneId", "")), str(item.get("itemId", ""))) for item in mapping.get("items", [])]
    timeline_items = timeline.get("items", [])
    timed_keys = [(str(item.get("sceneId", "")), str(item.get("itemId", ""))) for item in timeline_items]
    if not map_keys or map_keys != timed_keys:
        errors.append("B-roll 口播映射与时间线项目不一致")
    previous = -1
    for item in timeline_items:
        active, complete = item.get("activeAtMs"), item.get("completeAtMs")
        if not isinstance(active, (int, float)) or not isinstance(complete, (int, float)) or active < previous or complete <= active:
            errors.append(f"B-roll 时间线区间无效：{item.get('sceneId')}/{item.get('itemId')}")
            break
        previous = active
    for scene in driven:
        scene_id = str(scene.get("sceneId", scene.get("id", "")))
        composition_value = scene.get("compositionPath")
        composition = Path(composition_value) if composition_value else None
        if composition and not composition.is_absolute():
            composition = root / composition
        if not composition or not composition.is_file():
            continue
        source = composition.read_text(encoding="utf-8")
        if f'data-broll-progress-wired="{scene_id}"' not in source or "BrollProgressController.bindGsap" not in source:
            errors.append(f"B-roll {scene_id} 尚未接入共享运行时控制器")
        evidence["artifacts"].append({"sceneId": scene_id, "compositionPath": str(composition), "compositionHash": digest(composition)})
    evidence.update({"outlineHash": digest(outline_path), "mapPath": str(map_path), "mapHash": digest(map_path), "timelinePath": str(timeline_path), "timelineHash": digest(timeline_path), "audioEvidence": audio_evidence})
    return evidence, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--chapter", required=True)
    args = parser.parse_args()
    evidence, errors = validate(args.project_root, args.chapter)
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    print(json.dumps(evidence, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
