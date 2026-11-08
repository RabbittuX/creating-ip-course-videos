#!/usr/bin/env python3
"""Combine exact A-roll and B-roll review pages into one visual checkpoint."""

import argparse
import html
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aroll", required=True)
    parser.add_argument("--broll", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    sections = []
    for label, source in (("A-roll", args.aroll), ("B-roll", args.broll)):
        relative = os.path.relpath(Path(source).resolve(), output.parent)
        sections.append(f'<section><h2>{label}</h2><iframe title="{label}" src="{html.escape(relative)}"></iframe></section>')
    output.write_text("""<!doctype html><meta charset="utf-8"><title>Visual Review</title>
<style>body{margin:0;background:#111;color:#eee;font:16px system-ui;padding:24px}p{color:#aaa}section{margin:24px 0}iframe{width:100%;height:75vh;border:1px solid #555;border-radius:12px;background:white}</style>
<h1>A-roll + B-roll 联合视觉审核</h1><p>可在一页检查两类素材；批准仍按各自 build ID 独立记录。</p>""" + "".join(sections), encoding="utf-8")
    print(f"已生成联合审核页：{output}")


if __name__ == "__main__":
    main()
