#!/usr/bin/env python3
"""Validate canonical character references without semantic image judging."""

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(registry_path):
    registry_path = Path(registry_path).resolve()
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    errors = []
    seen = set()
    for item in data.get("characters", []):
        character_id = item.get("characterId")
        if not character_id or character_id in seen:
            errors.append(f"characterId 缺失或重复：{character_id}")
            continue
        seen.add(character_id)
        status = item.get("status")
        if status == "approved":
            value = item.get("canonicalPath")
            expected = item.get("sha256")
            if not value or not expected:
                errors.append(f"{character_id} 已批准但缺少路径或哈希")
                continue
            asset = (registry_path.parent / value).resolve()
            if not asset.is_file():
                errors.append(f"{character_id} 定稿资产不存在：{asset}")
            elif sha256(asset) != expected:
                errors.append(f"{character_id} 定稿资产哈希不匹配")
            if not item.get("identityInvariants"):
                errors.append(f"{character_id} 缺少 identityInvariants")
        elif status == "pending-user-asset":
            if item.get("canonicalPath") or item.get("sha256"):
                errors.append(f"{character_id} 待用户确认时不能预填定稿路径或哈希")
        else:
            errors.append(f"{character_id} 状态无效：{status}")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    args = parser.parse_args()
    errors = validate(args.registry)
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    print("角色定稿注册表校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
