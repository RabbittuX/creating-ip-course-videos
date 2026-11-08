#!/usr/bin/env python3
"""Build a static contact sheet for every B-roll template and component."""

import argparse
import html
import json
import os
import re
from pathlib import Path


def template_inner(source: str):
    match = re.search(r"<template[^>]*>(.*?)</template>", source, re.DOTALL | re.IGNORECASE)
    content = match.group(1) if match else source
    return re.sub(r"<script\b[^>]*>.*?</script>", "", content, flags=re.DOTALL | re.IGNORECASE)


def write_preview(source_path: Path, destination: Path, skill_root: Path):
    inner = template_inner(source_path.read_text(encoding="utf-8"))
    base = os.path.relpath(skill_root, destination.parent).replace(os.sep, "/") + "/"
    document = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<base href="{html.escape(base)}"><style>
html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:#252b31}}
[data-composition-id]{{left:0!important;right:auto!important;top:0!important;bottom:auto!important;width:1920px!important;height:1080px!important;transform-origin:0 0!important}}
</style></head><body>{inner}<script>
const reviewRoot=document.querySelector('[data-composition-id]');
function fitReview(){{const scale=innerWidth / 1920;reviewRoot.style.setProperty('transform',`scale(${{scale}})`,'important');}}
fitReview();addEventListener('resize',fitReview);
</script></body></html>'''
    destination.write_text(document, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="assets/broll directory")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    skill_root = root.parent.parent
    registry = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    output = Path(args.output).resolve()
    pages = output.parent / "pages"
    pages.mkdir(parents=True, exist_ok=True)

    entries = []
    for item in registry["templates"]:
        entries.append({
            "id": item["id"],
            "kind": "固定模板" if item.get("mode") == "fixed" else "模板库",
            "enabled": item.get("enabled", True),
            "source": root / item["source"],
        })
    for source in sorted((root / "library" / "components").glob("*.html")):
        entries.append({"id": source.stem, "kind": "共享组件", "enabled": True, "source": source})

    cards = []
    for index, item in enumerate(entries, 1):
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", item["id"])
        page = pages / f"{index:02d}-{slug}.html"
        write_preview(item["source"], page, skill_root)
        relative = page.relative_to(output.parent).as_posix()
        state = "可用" if item["enabled"] else "保留禁用"
        cards.append(
            f'<article class="preview-card"><iframe src="{html.escape(relative)}" '
            f'title="{html.escape(item["id"])}"></iframe><div class="meta">'
            f'<strong>{html.escape(item["id"])}</strong><span>{item["kind"]} · {state}</span></div></article>'
        )

    document = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>B-roll 背景全量审核</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#171b1f;color:#fff7ec;font:16px/1.5 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{max-width:1680px;margin:auto;padding:34px}}h1{{margin:0;font-size:38px}}.summary{{margin:10px 0 28px;color:#b8c1c9}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(500px,1fr));gap:22px}}.preview-card{{overflow:hidden;border:1px solid #71818e;border-radius:18px;background:#252b31;box-shadow:0 18px 46px rgba(0,0,0,.24)}}iframe{{display:block;width:100%;aspect-ratio:16/9;border:0;background:#252b31}}.meta{{display:flex;justify-content:space-between;gap:16px;padding:14px 18px;border-top:1px solid #71818e}}.meta strong{{color:#e9a51a}}.meta span{{color:#b8c1c9}}</style></head>
<body><main><h1>B-roll 模板背景全量审核</h1><p class="summary">24 个注册模板＋8 个共享组件。统一为 Skill 锁定的深色网格背景；“保留禁用”仅表示注册表状态未改变。</p><section class="grid">{"".join(cards)}</section></main></body></html>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    print(f"已生成 B-roll 背景审核页：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
