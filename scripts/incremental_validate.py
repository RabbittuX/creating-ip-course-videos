#!/usr/bin/env python3
"""Map changed files to the smallest chapter validation scope."""

import argparse
import json
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--changed", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.project).resolve()
    manifest = json.loads((root / "project.json").read_text(encoding="utf-8"))
    chapter_ids = [str(item["id"]) for item in manifest.get("chapters", [])]
    impacted = set()
    shared = False
    for changed in args.changed:
        resolved = Path(changed).resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError:
            relative = resolved.as_posix()
        match = re.search(r"(?:^|/)chapters/([^/]+)/", relative)
        order = re.search(r"(?:^|/)planning/work-orders/chapter-([^.\/]+)\.json$", relative)
        if match and match.group(1) in chapter_ids:
            impacted.add(match.group(1))
        elif order and order.group(1) in chapter_ids:
            impacted.add(order.group(1))
        else:
            shared = True
    if shared:
        impacted = set(chapter_ids)
    result = {"schemaVersion": 1, "changed": [str(Path(path).resolve()) for path in args.changed], "sharedChange": shared, "impactedChapters": sorted(impacted), "actions": [{"chapterId": chapter_id, "steps": ["validate", "preview", "render", "concatenate"]} for chapter_id in sorted(impacted)]}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"增量范围：{', '.join(result['impactedChapters']) or '无'}")


if __name__ == "__main__":
    main()
