#!/usr/bin/env python3
"""Build a concise chapter-by-chapter A/B-roll outline review."""

import argparse
import html
import json
from pathlib import Path

from validate_visual_outline import validate


def percent(value):
    return f"{float(value or 0) * 100:.1f}%"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outline", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    outline_path = Path(args.outline).resolve()
    data = json.loads(outline_path.read_text(encoding="utf-8"))
    _, errors = validate(outline_path)
    chapters = []
    for chapter in data.get("chapters", []):
        cid = str(chapter.get("chapterId", chapter.get("id", "")))
        stats = chapter.get("stats") or {}
        rows = []
        for scene in chapter.get("scenes", []):
            kind = str(scene.get("type", ""))
            origin = scene.get("designOrigin", "generated-aroll" if kind.lower().replace("-", "") == "aroll" else "")
            rows.append(f'''<tr><td>{html.escape(str(scene.get("sceneId", scene.get("id", ""))))}</td><td>{html.escape(kind)}</td><td>{html.escape(str(origin))}</td>
<td>{html.escape(str(scene.get("summary", "")))}</td><td>{html.escape(str(scene.get("sourceText", "")))}</td><td>{scene.get("sourceCharStart")}-{scene.get("sourceCharEnd")}</td><td>{float(scene.get("plannedDurationSeconds", 0) or 0):g}s</td></tr>''')
        chapters.append(f'''<section><h2>章节 {html.escape(cid)}</h2><p>A-roll {percent((stats.get("aroll") or {{}}).get("ratio"))} · B-roll {percent((stats.get("broll") or {{}}).get("ratio"))} · 总计 {stats.get("totalSeconds", 0)}s</p>
<table><thead><tr><th>ID</th><th>类型</th><th>来源</th><th>精简梗概</th><th>真实口播</th><th>字符范围</th><th>时长</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>''')
    overall = data.get("overallStats") or {}
    issues = "".join(f"<li>{html.escape(item)}</li>" for item in errors) or "<li>没有结构阻断项</li>"
    document = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>A/B-roll 视觉梗概审核</title>
<style>body{{margin:0;padding:34px;background:#252b31;color:#fff7ec;font:16px/1.5 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{max-width:1700px;margin:auto}}section,.issues{{background:#394149;border:1px solid #71818e;border-radius:18px;padding:20px;margin:18px 0}}h2{{color:#e9a51a}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #71818e;text-align:left;vertical-align:top}}</style>
<main><h1>A/B-roll 视觉梗概审核</h1><p>全片：A-roll {percent((overall.get("aroll") or {{}}).get("ratio"))} · B-roll {percent((overall.get("broll") or {{}}).get("ratio"))} · {overall.get("totalSeconds", 0)}s</p><div class="issues"><ul>{issues}</ul></div>{''.join(chapters)}</main></html>'''
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    print(f"已生成视觉梗概审核页：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
