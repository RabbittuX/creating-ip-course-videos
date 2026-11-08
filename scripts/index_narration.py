#!/usr/bin/env python3
"""Index one chapter into the canonical narration manifest."""

import argparse
import json
import sys
from pathlib import Path

from narration_contract import text_digest, validate_manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--chapter", required=True)
    parser.add_argument("--text-file", required=True)
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    project = json.loads((root / "project.json").read_text(encoding="utf-8"))
    expected = [str(item.get("id")) for item in project.get("chapters", [])]
    if str(args.chapter) not in expected:
        print(f"错误：未知章节 {args.chapter}", file=sys.stderr)
        return 2
    text = Path(args.text_file).read_text(encoding="utf-8").strip()
    if not text:
        print("错误：口播稿为空", file=sys.stderr)
        return 2
    target = root / "planning" / "narration-manifest.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    current = {str(item.get("chapterId")): item for item in data.get("chapters", [])}
    current[str(args.chapter)] = {"chapterId": str(args.chapter), "narration": text, "narrationHash": text_digest(text)}
    data["chapters"] = [current.get(cid, {"chapterId": cid, "narration": "", "narrationHash": None}) for cid in expected]
    data["status"] = "READY" if all(item.get("narration") for item in data["chapters"]) else "DRAFT"
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if data["status"] == "READY":
        _, errors = validate_manifest(root)
        if errors:
            for error in errors:
                print(f"错误：{error}", file=sys.stderr)
            return 2
    print(f"已索引章节 {args.chapter}；清单状态 {data['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
