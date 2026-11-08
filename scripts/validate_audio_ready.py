#!/usr/bin/env python3
"""Validate current chapter narration, audio, and word-alignment evidence."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from validate_aroll import load_json as load_aroll_json, validate_manifest as validate_aroll_manifest
from narration_contract import validate_manifest as validate_narration_manifest


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(project_root, chapter_id):
    root = Path(project_root).resolve()
    audio_dir = root / "chapters" / str(chapter_id) / "audio"
    manifest_path = audio_dir / "audio-ready.json"
    evidence = {"manifestPath": str(manifest_path), "chapterId": str(chapter_id)}
    errors = []
    arroll_path = root / "planning" / "aroll-manifest.json"
    profile_path = Path(__file__).resolve().parent.parent / "assets" / "presets" / "aroll-profile.json"
    if not arroll_path.is_file():
        errors.append("缺少 A-roll 清单，无法确认正式素材")
    else:
        arroll = load_aroll_json(arroll_path)
        arroll_errors, _ = validate_aroll_manifest(arroll, load_aroll_json(profile_path), "preview")
        errors.extend(f"A-roll 正式素材：{error}" for error in arroll_errors)
        evidence["arollManifestPath"] = str(arroll_path)
        evidence["arollManifestHash"] = digest(arroll_path)
    if not manifest_path.is_file():
        return evidence, ["缺少音频证据 audio-ready.json"]
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths = {}
    for key in ("narrationPath", "audioPath", "alignmentPath"):
        value = data.get(key)
        if not value:
            errors.append(f"音频证据缺少 {key}")
            continue
        path = Path(value)
        path = path if path.is_absolute() else audio_dir / path
        if not path.is_file():
            errors.append(f"音频产物不存在：{path}")
        paths[key] = path
    if errors:
        return evidence, errors
    for key, hash_key in (("narrationPath", "narrationHash"), ("audioPath", "audioHash"), ("alignmentPath", "alignmentHash")):
        current = digest(paths[key])
        if data.get(hash_key) != current:
            errors.append(f"{hash_key} 与当前文件不匹配")
        evidence[hash_key] = current
    narration = paths["narrationPath"].read_text(encoding="utf-8").strip()
    narration_evidence, narration_errors = validate_narration_manifest(root, chapter_id)
    errors.extend(narration_errors)
    if not narration_errors and narration != narration_evidence.get("canonicalNarration"):
        errors.append("音频口播与唯一主口播不一致")
    alignment = json.loads(paths["alignmentPath"].read_text(encoding="utf-8"))
    if alignment.get("audioHash") != evidence.get("audioHash"):
        errors.append("词级对齐不是由当前音频生成")
    if str(alignment.get("narration", "")).strip() != narration:
        errors.append("词级对齐口播与当前 narration.txt 不一致")
    tokens = alignment.get("tokens") or []
    previous_char = previous_time = 0
    if not tokens:
        errors.append("词级对齐没有 tokens")
    for token in tokens:
        start, end = token.get("charStart"), token.get("charEnd")
        start_ms, end_ms = token.get("startMs"), token.get("endMs")
        if not all(isinstance(value, (int, float)) for value in (start, end, start_ms, end_ms)) or start < previous_char or end <= start or start_ms < previous_time or end_ms <= start_ms:
            errors.append("词级 token 字符范围或时间顺序无效")
            break
        previous_char, previous_time = int(end), int(end_ms)
    if tokens and (int(tokens[0].get("charStart", -1)) != 0 or previous_char != len(narration)):
        errors.append("词级 token 未完整覆盖口播文本")
    evidence.update({"manifestHash": digest(manifest_path), "narrationPath": str(paths["narrationPath"]), "audioPath": str(paths["audioPath"]), "alignmentPath": str(paths["alignmentPath"]), **narration_evidence})
    return evidence, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--chapter", required=True)
    args = parser.parse_args()
    try:
        evidence, errors = validate(args.project_root, args.chapter)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"错误：音频证据无法校验：{exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    print(json.dumps(evidence, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
