#!/usr/bin/env python3
"""Write compact per-chapter readiness snapshots for resumable orchestration."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    root = Path(args.project).resolve()
    approvals = json.loads((root / "approvals.json").read_text(encoding="utf-8"))
    result = {"schemaVersion": 1, "project": str(root), "chapters": []}
    for chapter_id, item in sorted(approvals["chapters"].items()):
        milestones = item.get("milestones", {})
        accepted = item.get("approvals", {})
        missing = []
        chain = [
            (accepted.get("environment-cast"), "ENVIRONMENT_CAST_APPROVED"),
            (accepted.get("visual-outline"), "VISUAL_OUTLINE_APPROVED"),
            (accepted.get("aroll-images"), "AROLL_IMAGES_APPROVED"),
            (milestones.get("audio"), "AUDIO_READY"),
            (milestones.get("broll-sync"), "BROLL_SYNC_READY"),
            (milestones.get("preview-ready"), "PREVIEW_READY"),
            (accepted.get("preview"), "PREVIEW_APPROVED"),
            (milestones.get("rendered"), "RENDERED"),
            (milestones.get("final-qc"), "FINAL_QC_PASSED"),
            (milestones.get("delivery"), "DELIVERY_READY"),
        ]
        missing.extend(token for present, token in chain if not present)
        result["chapters"].append({"chapterId": chapter_id, "state": item.get("state", "DRAFT"), "missing": missing})
        status_path = root / "chapters" / chapter_id / "chapter-status.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        status_path.write_text(json.dumps(result["chapters"][-1], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output = Path(args.output) if args.output else root / "planning" / "chapter-status.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {len(result['chapters'])} 个章节状态")


if __name__ == "__main__":
    main()
