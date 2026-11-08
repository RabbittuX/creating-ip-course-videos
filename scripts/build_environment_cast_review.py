#!/usr/bin/env python3
"""Build a concise human review for chapter environments, cast, and action chains."""

import argparse
import html
import json
from pathlib import Path

from validate_environment_cast import validate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    plan = json.loads((root / "planning" / "environment-cast-plan.json").read_text(encoding="utf-8"))
    cards, all_errors = [], []
    for chapter in plan.get("chapters", []):
        cid = str(chapter.get("chapterId", chapter.get("id", "")))
        _, errors = validate(root, cid)
        all_errors.extend(f"章节 {cid}：{error}" for error in errors)
        background = chapter.get("background") or {}
        cast = ", ".join(str(item.get("characterId", "")) for item in chapter.get("cast", []))
        actions = "".join(f"<li>{html.escape(str(item))}</li>" for item in chapter.get("actionChain", []))
        scene_bible = chapter.get("sceneBible") or {}
        positions = "、".join(str(item) for item in scene_bible.get("actorPositions", []))
        location = str(background.get("locationType") or background.get("label") or "未命名场所")
        lighting = str(background.get("timeAndLighting") or "跟随场景自然光线")
        layout = str(background.get("spatialLayout") or scene_bible.get("environmentDescription", ""))
        props = background.get("keyProps") or []
        prop_chips = "".join(f'<span class="chip">{html.escape(str(item))}</span>' for item in props)
        cards.append(f'''<article>
<div class="chapter">章节 {html.escape(cid)}</div>
<h2>{html.escape(str(background.get("label", "")))}</h2>
<div class="location"><span>具体场所</span>{html.escape(location)}</div>
<div class="facts"><p><b>时间与光线</b>{html.escape(lighting)}</p><p><b>参演人物</b>{html.escape(cast)}</p></div>
<section><h3>空间布局</h3><p>{html.escape(layout)}</p></section>
<section><h3>关键道具</h3><div class="chips">{prop_chips or '<span class="muted">按场景描述配置</span>'}</div></section>
<section class="secondary"><p><b>换景理由</b>{html.escape(str(background.get("reason", "")))}</p><p><b>屏幕与墙面</b>{html.escape(str(scene_bible.get("screenBackground", "")))}</p><p><b>镜头位置</b>{html.escape(str(scene_bible.get("cameraFraming", "")))}</p><p><b>人物站位</b>{html.escape(positions)}</p></section>
<details><summary>展开查看连续动作链</summary><ol>{actions}</ol></details>
</article>''')
    issues = "".join(f"<li>{html.escape(item)}</li>" for item in all_errors) or "<li>没有结构阻断项</li>"
    document = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>A-roll 演绎背景与参演人物审核</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;padding:40px;background:#20262b;color:#fff8ee;font:17px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{max-width:1180px;margin:auto}}header{{margin-bottom:28px}}h1{{font-size:42px;margin:0 0 8px}}header p{{color:#bdc7cd;margin:0}}.issues{{font-size:14px;color:#8fe0c9;margin:18px 0}}.issues ul{{list-style:none;padding:0;margin:0}}article{{background:#343c43;border:1px solid #64727d;border-radius:22px;padding:28px;margin:22px 0;box-shadow:0 12px 30px #0003}}.chapter{{color:#9eabb4;font-size:14px;letter-spacing:.08em}}h2{{color:#f2b84b;font-size:30px;margin:4px 0 16px}}.location{{display:flex;align-items:center;gap:14px;background:#242b30;border-radius:14px;padding:16px 18px;font-size:25px;font-weight:700}}.location span{{font-size:13px;color:#20262b;background:#55d4b4;border-radius:999px;padding:5px 10px}}.facts{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:18px 0}}.facts p,.secondary p{{margin:0;background:#2b3238;border-radius:12px;padding:13px 15px}}b{{display:block;color:#91a0aa;font-size:13px;margin-bottom:4px}}section h3{{font-size:15px;color:#9eabb4;margin:18px 0 5px}}section p{{margin:0}}.chips{{display:flex;flex-wrap:wrap;gap:8px}}.chip{{background:#46515a;border:1px solid #687781;border-radius:999px;padding:6px 12px}}.secondary{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:20px}}details{{margin-top:18px;color:#d8e0e5}}summary{{cursor:pointer;color:#55d4b4}}ol{{margin-bottom:0}}.muted{{color:#91a0aa}}@media(max-width:760px){{body{{padding:20px}}.facts,.secondary{{grid-template-columns:1fr}}h1{{font-size:32px}}.location{{font-size:21px}}}}
</style>
<main><header><h1>A-roll 演绎背景审核</h1><p>这一页只审每章发生在哪里、空间长什么样、有哪些关键道具，以及谁在场。完整口播与哈希证据继续由后台校验。</p></header><section class="issues"><ul>{issues}</ul></section>{''.join(cards)}</main></html>'''
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    print(f"已生成背景与人物审核页：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
