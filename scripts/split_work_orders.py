#!/usr/bin/env python3
"""Split a video plan into compact, chapter-isolated work orders."""

import argparse
import hashlib
import json
from pathlib import Path


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    target = Path(path)
    return hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    plan_path = Path(args.project).resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    preset_hashes = {name: {"path": str(Path(path).resolve()), "sha256": file_hash(path)} for name, path in plan.get("presets", {}).items()}
    global_brief = {"schemaVersion": 1, "projectId": plan["projectId"], "title": plan.get("title", ""), "chapterCount": len(plan.get("chapters", [])), "sourcePlan": str(plan_path), "planHash": digest(plan), "presets": preset_hashes, "sharedPolicy": "read-only"}
    write(output / "global-brief.json", global_brief)
    base = Path(plan.get("outputRoot", plan_path.parent))
    for chapter in plan.get("chapters", []):
        core = {"chapter": chapter, "presetHashes": preset_hashes, "planHash": global_brief["planHash"]}
        order = {"schemaVersion": 1, "projectId": plan["projectId"], "chapterId": chapter["id"], "narration": chapter.get("narration", ""), "scenes": chapter.get("scenes", []), "inputHash": digest(core), "presetHashes": preset_hashes, "allowedWriteRoot": str(base / "chapters" / chapter["id"]), "contextPolicy": "isolated"}
        write(output / f"chapter-{chapter['id']}.json", order)
    print(f"已生成 {len(plan.get('chapters', []))} 份章节工作单：{output}")


if __name__ == "__main__":
    main()
