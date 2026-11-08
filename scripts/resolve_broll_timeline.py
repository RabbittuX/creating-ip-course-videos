#!/usr/bin/env python3
"""Resolve approved B-roll narration spans to word-aligned state times."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from validate_broll_narration_map import validate


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def token_at_char(position, tokens):
    covering = [token for token in tokens if int(token.get("charStart", -1)) <= position < int(token.get("charEnd", -1))]
    if covering:
        return covering[0]
    following = [token for token in tokens if int(token.get("charStart", -1)) >= position]
    return following[0] if following else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", required=True)
    parser.add_argument("--alignment", required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    mapping = json.loads(Path(args.map).read_text(encoding="utf-8"))
    errors = validate(mapping)
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    alignment = json.loads(Path(args.alignment).read_text(encoding="utf-8"))
    audio_hash = file_hash(args.audio)
    if alignment.get("audioHash") != audio_hash:
        print("错误：词级对齐对应的音频已经变化，必须重新对齐", file=sys.stderr)
        return 2
    tokens = alignment.get("tokens", [])
    resolved = []
    for item in mapping.get("items", []):
        switch_at = int(item.get("switchAtChar", item["sourceCharStart"]))
        start_token = token_at_char(switch_at, tokens)
        end_token = token_at_char(int(item["sourceCharEnd"]) - 1, tokens)
        if not start_token or not end_token:
            print(f"错误：{item.get('itemId')} 无法映射到词级对齐 token", file=sys.stderr)
            return 2
        resolved.append({
            **item,
            "switchAtChar": switch_at,
            "activeAtMs": int(start_token["startMs"]),
            "sourceEndsAtMs": int(end_token["endMs"]),
            "triggerTokenId": start_token.get("id"),
            "sourceEndTokenId": end_token.get("id"),
            "triggerToken": start_token.get("text"),
        })
    for index, item in enumerate(resolved):
        following = resolved[index + 1] if index + 1 < len(resolved) else None
        same_scene = following and following.get("sceneId") == item.get("sceneId")
        item["completeAtMs"] = following["activeAtMs"] if same_scene else item["sourceEndsAtMs"]
        item["states"] = {"before": "unvisited", "active": "yellow", "after": "green"}
    output = {
        "schemaVersion": 1,
        "chapterId": mapping.get("chapterId"),
        "alignmentHash": file_hash(args.alignment),
        "sourceAudioHash": audio_hash,
        "tolerance": {"milliseconds": 80, "frames": 2},
        "items": resolved,
        "finalState": {"allCompleted": True, "pointerVisible": False},
    }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已解析 {len(resolved)} 个 B-roll 状态触发点")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
