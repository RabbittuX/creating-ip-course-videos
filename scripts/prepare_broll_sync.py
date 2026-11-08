#!/usr/bin/env python3
"""Build chapter B-roll narration maps from the approved visual outline."""

import argparse
import json
import sys
from pathlib import Path

from build_broll_narration_map import build


def is_broll(scene):
    value = str(scene.get("type", scene.get("kind", ""))).lower().replace("_", "-")
    return value in {"b-roll", "broll"}


def chapter_id(chapter):
    return str(chapter.get("chapterId", chapter.get("id", "")))


def validate_scene(scene, label):
    errors = []
    mode = scene.get("progressMode")
    if mode not in {"static", "narration-driven"}:
        errors.append(f"{label} 必须声明 progressMode: static|narration-driven")
    if mode == "narration-driven":
        items = scene.get("items") or []
        if not items:
            errors.append(f"{label} 口播驱动 B-roll 缺少 items")
        for index, item in enumerate(items, 1):
            if not item.get("itemId") or not str(item.get("sourceText", "")).strip():
                errors.append(f"{label} 第 {index} 项缺少 itemId/sourceText")
    return errors


def prepare(project_root, outline_path=None):
    root = Path(project_root).resolve()
    path = Path(outline_path).resolve() if outline_path else root / "planning" / "visual-outline.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    outputs = []
    if data.get("status") != "APPROVED":
        errors.append("visual-outline 还未标记为 APPROVED")
    for chapter in data.get("chapters", []):
        cid = chapter_id(chapter)
        if not cid:
            errors.append("visual-outline 章节缺少 chapterId/id")
            continue
        narration = str(chapter.get("narration", ""))
        flat_items = []
        for scene in chapter.get("scenes", []):
            if not is_broll(scene):
                continue
            scene_id = str(scene.get("sceneId", scene.get("id", "")))
            label = f"章节 {cid} / B-roll {scene_id or '<missing-scene-id>'}"
            errors.extend(validate_scene(scene, label))
            if scene.get("progressMode") != "narration-driven":
                continue
            if not scene_id:
                errors.append(f"{label} 缺少 sceneId")
                continue
            flat_items.extend({**item, "sceneId": scene_id} for item in scene.get("items", []))
        mapping, build_errors = build({"chapterId": cid, "narration": narration, "items": flat_items})
        errors.extend(f"章节 {cid}: {message}" for message in build_errors)
        outputs.append((cid, mapping))
    if errors:
        return [], errors
    for cid, mapping in outputs:
        target = root / "chapters" / cid / "planning" / "broll-narration-map.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [str(root / "chapters" / cid / "planning" / "broll-narration-map.json") for cid, _ in outputs], []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--outline")
    args = parser.parse_args()
    try:
        outputs, errors = prepare(args.project_root, args.outline)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"错误：无法读取 visual-outline：{exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    print(f"已从 visual-outline 自动生成 {len(outputs)} 个章节的 B-roll 口播映射")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
