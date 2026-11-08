#!/usr/bin/env python3
"""Record and check content-addressed production artifacts."""

import argparse
import hashlib
import json
from pathlib import Path


def hash_file(path):
    target = Path(path).resolve()
    return {"path": str(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


def fingerprint(paths):
    values = sorted((hash_file(path) for path in paths), key=lambda item: item["path"])
    raw = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest(), values


def load(path):
    target = Path(path)
    return json.loads(target.read_text(encoding="utf-8")) if target.exists() else {"schemaVersion": 1, "records": {}}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("record", "check"):
        action = sub.add_parser(command)
        action.add_argument("--cache", required=True)
        action.add_argument("--key", required=True)
        action.add_argument("--input", action="append", required=True)
        if command == "record":
            action.add_argument("--artifact", action="append", required=True)
    args = parser.parse_args()
    cache_path = Path(args.cache)
    data = load(cache_path)
    value, inputs = fingerprint(args.input)
    record = data["records"].get(args.key)
    if args.command == "check":
        artifacts_ok = bool(record)
        if record:
            for artifact in record.get("artifacts", []):
                path = Path(artifact["path"])
                artifacts_ok = artifacts_ok and path.is_file() and hash_file(path)["sha256"] == artifact["sha256"]
        if record and record.get("inputHash") == value and artifacts_ok:
            print(f"CACHE_HIT {args.key}")
            return 0
        print(f"CACHE_MISS {args.key}")
        return 3
    data["records"][args.key] = {"inputHash": value, "inputs": inputs, "artifacts": [hash_file(path) for path in args.artifact]}
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"CACHE_RECORDED {args.key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
