#!/usr/bin/env python3
"""Create a resumable chapter-oriented course workspace."""

import argparse
import json
from pathlib import Path

import user_config as uc


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--chapters", required=True, help="Comma-separated chapter IDs")
    args = parser.parse_args()
    root = Path(args.root)
    skill_root = Path(__file__).resolve().parent.parent
    chapters = [x.strip() for x in args.chapters.split(",") if x.strip()]
    for name in ("reviews", "renders", "locks", "audio", "captions", "chapters", "planning", "timing", "cache", "scene-bibles", "preview"):
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / "planning" / "work-orders").mkdir(parents=True, exist_ok=True)
    for name in ("candidates", "approved"):
        (root / "assets" / "arroll" / name).mkdir(parents=True, exist_ok=True)
        (root / "assets" / "broll" / name).mkdir(parents=True, exist_ok=True)
    for chapter_id in chapters:
        for name in ("aroll", "broll", "preview"):
            (root / "chapters" / chapter_id / name).mkdir(parents=True, exist_ok=True)
        (root / "chapters" / chapter_id / "planning").mkdir(parents=True, exist_ok=True)
        (root / "chapters" / chapter_id / "timing").mkdir(parents=True, exist_ok=True)
        write_json(root / "chapters" / chapter_id / "chapter-status.json", {"chapterId": chapter_id, "state": "NARRATION_INDEXED", "missing": ["ENVIRONMENT_CAST_APPROVED"]})
        write_json(root / "chapters" / chapter_id / "planning" / "broll-narration-map.json", {"schemaVersion": 1, "chapterId": chapter_id, "narration": "", "items": []})
        write_json(root / "chapters" / chapter_id / "timing" / "broll-state-timeline.json", {"schemaVersion": 1, "chapterId": chapter_id, "alignmentHash": None, "items": []})
        write_json(root / "chapters" / chapter_id / "timing" / "captions.json", {"schemaVersion": 1, "chapterId": chapter_id, "status": "DRAFT", "alignmentHash": None, "sourceAudioHash": None, "captions": []})
        write_json(root / "chapters" / chapter_id / "timing" / "chapter-timeline.json", {"schemaVersion": 1, "chapterId": chapter_id, "status": "DRAFT", "durationMs": None, "titleWindow": None, "stingWindow": None, "narrationWindow": None, "captions": []})
    manifest = {
        "schemaVersion": 3,
        "projectId": args.project_id,
        "skill": "creating-ip-course-videos",
        "chapters": [{"id": chapter_id, "state": "NARRATION_INDEXED", "previewBuildId": None, "approvedBuildId": None} for chapter_id in chapters],
        "captions": [],
        "fixedArollRegistry": str((skill_root / "assets" / "arroll" / "template-registry.json").resolve()),
        "narrationManifest": "planning/narration-manifest.json",
        "arollManifest": "planning/aroll-manifest.json",
        "brollManifest": "planning/broll-manifest.json",
        "brollProgressController": str((skill_root / "assets" / "broll" / "broll-progress-controller.js").resolve()),
        "brollLock": "locks/broll-selection.json",
        "approvalFile": "approvals.json",
        "workOrderRoot": "planning/work-orders",
        "cacheFile": "cache/artifacts.json",
        "characterRegistry": str(uc.character_registry_path().resolve()),
        "environmentCastPlan": "planning/environment-cast-plan.json",
        "visualOutline": "planning/visual-outline.json",
        "creativeDirectives": "planning/creative-directives.json",
        "fullTimeline": "timing/full-timeline.json",
        "execution": {"mode": "gated", "maxWorkers": 3, "contextPolicy": "isolated", "arollChapterOrder": "serial"},
    }
    approvals = {
        "schemaVersion": 3,
        "chapters": {
            chapter_id: {
                "state": "NARRATION_INDEXED",
                "milestones": {"audio": None, "broll-sync": None, "preview-ready": None, "rendered": None, "final-qc": None, "delivery": None},
                "requests": {"environment-cast": None, "visual-outline": None, "aroll-images": None, "preview": None},
                "approvals": {"environment-cast": None, "visual-outline": None, "aroll-images": None, "preview": None},
                "history": [],
            } for chapter_id in chapters
        },
    }
    arroll = {
        "schemaVersion": 1,
        "projectId": args.project_id,
        "candidateRoot": str((root / "assets" / "arroll" / "candidates").resolve()),
        "approvedRoot": str((root / "assets" / "arroll" / "approved").resolve()),
        "environmentCastPlan": str((root / "planning" / "environment-cast-plan.json").resolve()),
        "characterRegistry": str(uc.character_registry_path().resolve()),
        "sequences": [],
        "candidates": [],
        "approvals": {},
    }
    broll = {
        "schemaVersion": 1,
        "projectId": args.project_id,
        "candidateRoot": str((root / "assets" / "broll" / "candidates").resolve()),
        "approvedRoot": str((root / "assets" / "broll" / "approved").resolve()),
        "candidates": [],
        "approvals": {},
        "selectionAudit": {"functionalSceneCount": 0, "uses": []},
    }
    slots = uc.materialize_slots(root / "assets" / "ip-reference")
    import shutil
    (root / "assets" / "textures").mkdir(parents=True, exist_ok=True)
    shutil.copy2(skill_root / "assets" / "textures" / "paper-texture.png", root / "assets" / "textures" / "paper-texture.png")
    manifest["characterSlots"] = {"dir": "assets/ip-reference", "sources": slots}
    write_json(root / "project.json", manifest)
    write_json(root / "approvals.json", approvals)
    write_json(root / "planning" / "aroll-manifest.json", arroll)
    write_json(root / "planning" / "broll-manifest.json", broll)
    write_json(root / "planning" / "narration-manifest.json", {"schemaVersion": 1, "status": "DRAFT", "chapters": [{"chapterId": chapter_id, "narration": "", "narrationHash": None} for chapter_id in chapters]})
    write_json(root / "planning" / "environment-cast-plan.json", {"schemaVersion": 1, "status": "DRAFT", "chapters": []})
    write_json(root / "planning" / "visual-outline.json", {"schemaVersion": 1, "status": "DRAFT", "durationBasis": "planned", "chapters": [], "overallStats": {}})
    write_json(root / "planning" / "creative-directives.json", {"schemaVersion": 1, "directives": []})
    write_json(root / "timing" / "full-timeline.json", {"schemaVersion": 1, "projectId": args.project_id, "status": "DRAFT", "durationMs": None, "chapters": []})
    if not uc.is_configured():
        print(f"提醒：未找到用户配置（{uc.config_path()}），本项目使用的是示例占位角色。运行 scripts/setup_config.py --init 配置你自己的 IP 人物。")
    print(f"已创建项目：{root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
