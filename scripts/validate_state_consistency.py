#!/usr/bin/env python3
"""Ensure project chapter states agree with authoritative approval evidence."""

import argparse
import json
import sys
from pathlib import Path

from approval_gate import available_tokens, ORDER


def derived_state(item):
    have = available_tokens(item)
    return next((token for token in reversed(ORDER) if token in have), "NARRATION_INDEXED")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--approvals", required=True)
    args = parser.parse_args()
    project = json.loads(Path(args.project).read_text(encoding="utf-8"))
    approvals = json.loads(Path(args.approvals).read_text(encoding="utf-8"))
    errors = []
    for chapter in project.get("chapters", []):
        chapter_id = chapter.get("id")
        evidence = approvals.get("chapters", {}).get(chapter_id)
        if not evidence:
            errors.append(f"章节 {chapter_id} 缺少审批证据")
            continue
        expected = derived_state(evidence)
        if chapter.get("state") != expected or evidence.get("state") != expected:
            errors.append(f"章节 {chapter_id} 状态不一致：project={chapter.get('state')} approvals={evidence.get('state')} derived={expected}")
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    print("项目状态与审批证据一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
