#!/usr/bin/env python3
"""Create a bounded queue of dependency-ready, isolated chapter jobs."""

import argparse
import json
from pathlib import Path

from user_config import character_registry_path


REFERENCES = {
    "environment-cast": ["references/planning-review-system.md", "references/character-reference-system.md"],
    "visual-outline": ["references/planning-review-system.md", "references/broll-template-system.md"],
    "aroll": ["references/aroll-continuity.md", "references/aroll-review-system.md", "references/ip-character-lock.md", "references/visual-system.md", "references/character-reference-system.md"],
    "audio": ["references/tts-caption-audio.md", "references/subtitle-segmentation.md"],
    "broll-preview": ["references/broll-template-system.md", "references/broll-narration-sync.md", "references/subtitle-segmentation.md", "references/visual-system.md"],
    "preview": ["references/approval-gates.md"],
}


def job(root, chapter_id, stage):
    return {
        "jobId": f"{chapter_id}:{stage}",
        "chapterId": chapter_id,
        "stage": stage,
        "workOrder": str(root / "planning" / "work-orders" / f"chapter-{chapter_id}.json"),
        "allowedWriteRoot": str(root / "chapters" / chapter_id),
        "contextPolicy": "isolated",
        "requiredReferences": REFERENCES[stage],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.max_workers < 1:
        raise SystemExit("--max-workers 必须大于 0")
    root = Path(args.project).resolve()
    approvals = json.loads((root / "approvals.json").read_text(encoding="utf-8"))
    queue = []
    chapters = sorted(approvals["chapters"].items())
    if any(not item.get("approvals", {}).get("environment-cast") for _, item in chapters):
        for chapter_id, item in chapters:
            if not item.get("approvals", {}).get("environment-cast") and not item.get("requests", {}).get("environment-cast"):
                queue.append(job(root, chapter_id, "environment-cast"))
    elif any(not item.get("approvals", {}).get("visual-outline") for _, item in chapters):
        for chapter_id, item in chapters:
            if not item.get("approvals", {}).get("visual-outline") and not item.get("requests", {}).get("visual-outline"):
                queue.append(job(root, chapter_id, "visual-outline"))
    elif any(not item.get("approvals", {}).get("aroll-images") for _, item in chapters):
        for chapter_id, item in chapters:
            if not item.get("approvals", {}).get("aroll-images"):
                if not item.get("requests", {}).get("aroll-images"):
                    queue.append(job(root, chapter_id, "aroll"))
                break
    else:
        for chapter_id, item in chapters:
            milestones = item.get("milestones", {})
            accepted = item.get("approvals", {})
            requested = item.get("requests", {})
            if not milestones.get("audio"):
                queue.append(job(root, chapter_id, "audio"))
            elif not milestones.get("broll-sync"):
                queue.append(job(root, chapter_id, "broll-preview"))
            elif milestones.get("preview-ready") and not accepted.get("preview") and not requested.get("preview"):
                queue.append(job(root, chapter_id, "preview"))
    result = {
        "schemaVersion": 1,
        "maxWorkers": args.max_workers,
        "activeBatch": queue[:args.max_workers],
        "readyQueue": queue,
        "sharedReadOnly": [str(root / "planning" / "work-orders" / "global-brief.json"), "assets/presets", str(character_registry_path()), "assets/arroll/template-registry.json", "assets/broll/template-registry.json"],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"可并行任务 {len(queue)} 个；当前批次 {len(result['activeBatch'])} 个")


if __name__ == "__main__":
    main()
