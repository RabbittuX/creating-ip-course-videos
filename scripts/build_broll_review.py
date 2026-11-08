#!/usr/bin/env python3
"""Build a review page with live B-roll source and machine-inspection evidence."""

import argparse
import html
import json
import os
import re
import shutil
from pathlib import Path

from validate_broll import load_json, validate_manifest


def build_live_preview(source, destination):
    raw = source.read_text(encoding="utf-8")
    match = re.search(r"<template[^>]*>(.*?)</template>", raw, re.DOTALL | re.IGNORECASE)
    if not match:
        shutil.copy2(source, destination)
        return
    inner = match.group(1)
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", inner, re.DOTALL | re.IGNORECASE)
    markup = re.sub(r"<script\b[^>]*>.*?</script>", "", inner, flags=re.DOTALL | re.IGNORECASE)
    base = os.path.relpath(source.parent.resolve(), destination.parent.resolve()).replace(os.sep, "/") + "/"
    composition = re.search(r'data-composition-id=["\']([^"\']+)', markup)
    composition_id = composition.group(1) if composition else ""
    document = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><base href="{html.escape(base)}">
<style>html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:#252b31}}[data-composition-id]{{left:0!important;top:0!important;transform-origin:0 0!important}}</style>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js"></script></head><body>{markup}
<script>{''.join(scripts)}
const root=document.querySelector('[data-composition-id]');
function fit(){{if(!root)return;const w=Number(root.dataset.width||1920),h=Number(root.dataset.height||1080);root.style.transform=`scale(${{Math.min(innerWidth/w,innerHeight/h)}})`;}}
fit();addEventListener('resize',fit);const timeline=window.__timelines&&window.__timelines[{json.dumps(composition_id)}];if(timeline)timeline.play(0);
</script></body></html>'''
    destination.write_text(document, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    data = load_json(args.manifest)
    profile = load_json(args.profile)
    errors, warnings = validate_manifest(data, profile, "review")
    output = Path(args.output)
    media = output.parent / "media"
    media.mkdir(parents=True, exist_ok=True)
    cards = []
    for item in data.get("candidates", []):
        candidate_id = str(item.get("candidateId", "unknown"))
        source = Path(str(item.get("sourcePath", "")))
        relative = ""
        if source.is_file():
            target = media / f"{candidate_id}{source.suffix.lower()}"
            build_live_preview(source, target)
            relative = target.relative_to(output.parent).as_posix()
        frames = item.get("inspection", {}).get("sampledFrames", [])
        frame_rows = "".join(
            f"<tr><td>{html.escape(str(x.get('time')))}</td><td>{x.get('textOverflowCount', 0)}</td>"
            f"<td>{x.get('focusMisalignedCount', 0)}</td><td>{'是' if x.get('whiteFrame') else '否'}</td></tr>"
            for x in frames
        )
        timeline = html.escape(json.dumps(item.get("stateTimeline", []), ensure_ascii=False, indent=2))
        cards.append(f'''<article><header><h2>{html.escape(candidate_id)}</h2><span>{html.escape(str(item.get("status", "REVIEW")))}</span></header>
<p><b>Template ID：</b>{html.escape(str(item.get("templateId", "")))} · <b>Family：</b>{html.escape(str(item.get("family", "")))}</p>
<p><b>素材哈希：</b><code>{html.escape(str(item.get("sourceHash", "")))}</code></p>
<p><b>对应口播：</b>{html.escape(str(item.get("narrationCue", "")))}</p>
<h3>动画预览</h3>{f'<iframe src="{html.escape(relative)}"></iframe>' if relative else '<div class="missing">缺少动画源</div>'}
<h3>关键帧检查</h3><table><thead><tr><th>时间</th><th>溢出</th><th>焦点错位</th><th>白帧</th></tr></thead><tbody>{frame_rows}</tbody></table>
<h3>状态时间线</h3><pre>{timeline}</pre></article>''')
    issue_items = "".join(f"<li>{html.escape(x)}</li>" for x in errors) or "<li>没有阻断项</li>"
    warning_items = "".join(f"<li>{html.escape(x)}</li>" for x in warnings)
    document = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>B-roll 审核</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#252b31;color:#fff7ec;font:17px/1.5 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{max-width:1540px;margin:auto;padding:32px}}article,.summary{{background:#394149;border:1px solid #71818e;border-radius:18px;padding:22px;margin:18px 0}}header{{display:flex;justify-content:space-between}}header span{{background:#e9a51a;color:#252b31;padding:6px 12px;border-radius:999px}}iframe{{width:100%;aspect-ratio:16/9;border:2px solid #55d4b4;border-radius:12px;background:#252b31}}table{{width:100%;border-collapse:collapse}}th,td{{border-bottom:1px solid #71818e;padding:9px;text-align:left}}pre{{white-space:pre-wrap;background:#252b31;padding:14px;border-radius:10px}}code{{word-break:break-all}}.error{{color:#ffaaa0}}.warning{{color:#ffd36a}}</style></head><body><main><h1>{html.escape(str(data.get('projectId', '')))} · B-roll 审核</h1>
<section class="summary"><p>审核顺序：动画预览 → 首尾及关键帧 → 口播同步 → 状态推进 → 真实页面溯源。</p><ul class="error">{issue_items}</ul><ul class="warning">{warning_items}</ul></section>{''.join(cards)}</main></body></html>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    print(f"已生成 B-roll 审核页：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
