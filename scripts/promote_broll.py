#!/usr/bin/env python3
"""Promote an approved B-roll candidate and register it as a reusable template."""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from validate_broll import load_json, sha256, validate_manifest


def save_atomic(path, data):
    target = Path(path)
    pending = target.with_suffix(target.suffix + ".pending")
    pending.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pending.replace(target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--registry", required=True)
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
    candidate = next(x for x in data["candidates"] if x.get("candidateId") == args.candidate_id)
    source = Path(candidate["sourcePath"])
    approved_root = Path(data["approvedRoot"])
    approved_root.mkdir(parents=True, exist_ok=True)
    destination = approved_root / f"{candidate['templateId']}{source.suffix.lower()}"
    shutil.copy2(source, destination)
    if sha256(destination) != candidate["sourceHash"]:
        print("错误：晋级后的 B-roll 哈希不一致", file=sys.stderr)
        return 2

    registry_path = Path(args.registry)
    registry = load_json(registry_path)
    entry = dict(candidate.get("registryEntry") or {})
    if not entry or entry.get("id") != candidate.get("templateId"):
        print("错误：registryEntry 缺失或 templateId 不一致", file=sys.stderr)
        return 2
    if any(x.get("id") == entry["id"] for x in registry.get("templates", [])):
        print(f"错误：模板 ID 已存在：{entry['id']}", file=sys.stderr)
        return 2
    try:
        entry["source"] = destination.resolve().relative_to(registry_path.parent.resolve()).as_posix()
    except ValueError:
        entry["source"] = os.path.relpath(destination.resolve(), registry_path.parent.resolve())
    registry.setdefault("templates", []).append(entry)

    candidate["approvedSourcePath"] = str(destination)
    candidate["status"] = "APPROVED"
    data.setdefault("approvals", {})[args.candidate_id] = {
        "sourceHash": candidate["sourceHash"],
        "approvedBy": args.approved_by,
        "approvedAt": datetime.now(timezone.utc).isoformat(),
        "registeredTemplateId": entry["id"],
    }
    save_atomic(registry_path, registry)
    save_atomic(args.manifest, data)
    print(f"已晋级并注册 B-roll：{args.candidate_id} → {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
