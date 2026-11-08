#!/usr/bin/env python3
"""Recompute planned A/B-roll duration ratios in the visual outline."""

import argparse
import json
from pathlib import Path

from validate_visual_outline import ratio_stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outline", required=True)
    args = parser.parse_args()
    path = Path(args.outline)
    data = json.loads(path.read_text(encoding="utf-8"))
    all_scenes = []
    for chapter in data.get("chapters", []):
        scenes = chapter.get("scenes") or []
        chapter["stats"] = ratio_stats(scenes)
        all_scenes.extend(scenes)
    data["overallStats"] = ratio_stats(all_scenes)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已更新 {len(data.get('chapters', []))} 个章节的 A/B-roll 时长统计")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
