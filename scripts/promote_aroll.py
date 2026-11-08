#!/usr/bin/env python3
"""Promote one explicitly approved A-roll candidate into the production asset root."""

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from validate_aroll import load_json, sha256, validate_manifest


def save_atomic(path, data):
    target = Path(path)
    pending = target.with_suffix(target.suffix + ".pending")
    pending.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pending.replace(target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--approved-by", required=True)
    args = parser.parse_args()
    data = load_json(args.manifest)
    profile = load_json(args.profile)
    errors, warnings = validate_manifest(data, profile, "review", [args.candidate_id])
    for warning in warnings:
        print(f"警告：{warning}")
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2

    candidate = next(
        item for item in data["candidates"] if item.get("candidateId") == args.candidate_id
    )
    source = Path(candidate["assetPath"])
    approved_root = Path(data["approvedRoot"])
    approved_root.mkdir(parents=True, exist_ok=True)
    destination = approved_root / f"{args.candidate_id}{source.suffix.lower()}"
    shutil.copy2(source, destination)
    if sha256(destination) != candidate["assetHash"]:
        print("错误：晋级后的正式素材哈希不一致", file=sys.stderr)
        return 2

    candidate["approvedAssetPath"] = str(destination)
    candidate["status"] = "APPROVED"
    data.setdefault("approvals", {})[args.candidate_id] = {
        "assetHash": candidate["assetHash"],
        "approvedBy": args.approved_by,
        "approvedAt": datetime.now(timezone.utc).isoformat(),
    }
    save_atomic(args.manifest, data)
    print(f"已晋级 A-roll：{args.candidate_id} → {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
