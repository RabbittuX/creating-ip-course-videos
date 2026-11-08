#!/usr/bin/env python3
"""Audit every registered B-roll template and shared component for the locked canvas."""

import argparse
import json
import re
import sys
from pathlib import Path


REQUIRED_SNIPPETS = (
    'data-broll-theme="locked-grid-v1"',
    'data-broll-theme-root="locked-grid-v1"',
    'data-broll-background="locked-grid-v1"',
    "background-color:#252b31",
    "radial-gradient(circle at 50% 0%,rgba(78,95,109,.18),transparent 60%)",
    "linear-gradient(rgba(132,153,171,.10) 1px,transparent 1px)",
    "linear-gradient(90deg,rgba(132,153,171,.10) 1px,transparent 1px)",
    "background-size:auto,44px 44px,44px 44px",
)


def inspect(path: Path, expected_background: str):
    issues = []
    source = path.read_text(encoding="utf-8")
    for snippet in REQUIRED_SNIPPETS:
        if snippet not in source:
            issues.append(f"缺少规范片段：{snippet}")
    if source.count('data-broll-background="locked-grid-v1"') != 1:
        issues.append("锁定背景层数量必须为 1")
    if expected_background != "#252b31":
        issues.append(f"品牌配置中的 B-roll 背景不是 #252b31：{expected_background}")
    root = re.search(r'<div\b(?=[^>]*data-composition-id="[^"]+")[^>]*>', source)
    if not root or 'data-broll-theme-root="locked-grid-v1"' not in root.group(0):
        issues.append("composition root 未绑定锁定主题")
    return issues


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--tokens", required=True)
    args = parser.parse_args()
    registry_path = Path(args.registry)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    tokens = json.loads(Path(args.tokens).read_text(encoding="utf-8"))
    broll_root = registry_path.parent
    templates = [broll_root / item["source"] for item in registry["templates"]]
    components = sorted((broll_root / "library" / "components").glob("*.html"))
    results = []
    for kind, paths in (("template", templates), ("component", components)):
        for path in paths:
            issues = ["文件不存在"] if not path.is_file() else inspect(
                path, tokens["colors"]["brollBackground"]
            )
            results.append({"kind": kind, "path": str(path), "issues": issues})
    failed = [item for item in results if item["issues"]]
    report = {
        "schemaVersion": 1,
        "templateCount": len(templates),
        "componentCount": len(components),
        "passedCount": len(results) - len(failed),
        "failedCount": len(failed),
        "results": results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
