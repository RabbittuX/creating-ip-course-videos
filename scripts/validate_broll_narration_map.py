#!/usr/bin/env python3
"""Validate narration spans and unique B-roll trigger signals."""

import argparse
import json
import sys
from pathlib import Path


def validate(data):
    narration = data.get("narration", "")
    errors = []
    previous = -1
    ids = set()
    for index, item in enumerate(data.get("items", []), 1):
        label = item.get("itemId") or f"#{index}"
        if label in ids:
            errors.append(f"itemId 重复：{label}")
        ids.add(label)
        start = item.get("sourceCharStart")
        end = item.get("sourceCharEnd")
        has_switch_at = "switchAtChar" in item
        switch_at = item.get("switchAtChar", start)
        trigger = str(item.get("triggerText", ""))
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start or end > len(narration):
            errors.append(f"{label} 原文字符范围无效：{start}-{end}")
            continue
        if start < previous:
            errors.append(f"{label} 原文范围顺序倒退")
        previous = start
        if not isinstance(switch_at, int) or switch_at < start or switch_at >= end:
            errors.append(f"{label} switchAtChar 不在原文范围内")
        if not trigger:
            errors.append(f"{label} 缺少 triggerText")
            continue
        occurrences = [i for i in range(len(narration)) if narration.startswith(trigger, i)]
        occurrence = item.get("triggerOccurrence")
        if len(occurrences) > 1 and not occurrence and not has_switch_at:
            errors.append(f"{label} 触发短语不唯一；请延长信号或填写 triggerOccurrence/上下文")
        elif occurrence and (occurrence < 1 or occurrence > len(occurrences)):
            errors.append(f"{label} triggerOccurrence 超出匹配数量")
        expected = switch_at if has_switch_at and narration.startswith(trigger, switch_at) else (occurrences[(occurrence or 1) - 1] if occurrences else -1)
        if expected < start or expected >= end:
            errors.append(f"{label} 触发短语不在声明的原文范围内")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", required=True)
    args = parser.parse_args()
    errors = validate(json.loads(Path(args.map).read_text(encoding="utf-8")))
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    print("B-roll 口播映射校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
