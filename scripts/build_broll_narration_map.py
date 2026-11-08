#!/usr/bin/env python3
"""Build lightweight B-roll summary-to-narration character mappings."""

import argparse
import json
import sys
from pathlib import Path


def locate(text, needle, cursor, occurrence=None):
    starts = []
    at = text.find(needle)
    while at >= 0:
        starts.append(at)
        at = text.find(needle, at + 1)
    if not starts:
        return None
    if occurrence is not None:
        return starts[int(occurrence) - 1] if 0 < int(occurrence) <= len(starts) else None
    return next((start for start in starts if start >= cursor), None)


def build(data):
    narration = str(data.get("narration", ""))
    errors, output, cursor = [], [], 0
    for index, item in enumerate(data.get("items", []), 1):
        label = item.get("itemId") or f"#{index}"
        source = str(item.get("sourceText", ""))
        if not source:
            errors.append(f"{label} 缺少 sourceText")
            continue
        start = locate(narration, source, cursor, item.get("sourceOccurrence"))
        if start is None:
            errors.append(f"{label} 无法在口播中定位 sourceText")
            continue
        end = start + len(source)
        switch_text = str(item.get("switchText", ""))
        if switch_text:
            local = source.find(switch_text)
            if local < 0:
                errors.append(f"{label} 的 switchText 不在 sourceText 中")
                continue
            switch_at = start + local
        else:
            switch_at = start
        trigger = narration[switch_at:min(end, switch_at + 12)].strip()
        output.append({
            **item,
            "sourceCharStart": start,
            "sourceCharEnd": end,
            "switchAtChar": switch_at,
            "triggerText": trigger,
            "targetId": item.get("targetId") or item.get("itemId"),
            "mappingStatus": "resolved",
        })
        cursor = end
    return {"schemaVersion": 2, "chapterId": data.get("chapterId"), "narration": narration, "items": output}, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result, errors = build(json.loads(Path(args.input).read_text(encoding="utf-8")))
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已建立 {len(result['items'])} 个 B-roll 口播映射")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
