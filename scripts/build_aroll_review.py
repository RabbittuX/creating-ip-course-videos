#!/usr/bin/env python3
"""Build a media-backed A-roll review page from the candidate manifest."""

import argparse
import html
import json
import shutil
from pathlib import Path

from validate_aroll import load_json, validate_manifest


LABELS = {
    "full": "完整画面",
    "face": "面部",
    "screenLeftEye": "画面左眼",
    "screenRightEye": "画面右眼",
}


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
    media_dir = output.parent / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    cards = []
    for candidate in data.get("candidates", []):
        candidate_id = str(candidate.get("candidateId", "unknown"))
        images = []
        for key in profile.get("reviewCrops", ["full"]):
            source_value = candidate.get("crops", {}).get(key)
            if key == "full" and not source_value:
                source_value = candidate.get("assetPath")
            if not source_value or not Path(source_value).is_file():
                images.append(f'<figure class="missing"><div class="missing-frame">缺少图片</div><figcaption>{html.escape(LABELS.get(key, key))}</figcaption></figure>')
                continue
            source = Path(source_value)
            target = media_dir / f"{candidate_id}-{key}{source.suffix.lower()}"
            shutil.copy2(source, target)
            relative = target.relative_to(output.parent).as_posix()
            if key == "full":
                images.append(f'<figure><div class="aroll-paper" data-aroll-paper><div class="aroll-stage" data-aroll-stage><img src="{html.escape(relative)}" alt="完整画面"></div><div class="subtitle-safe" data-subtitle-safe-zone>字幕安全区</div></div><figcaption>最终屏幕框预览</figcaption></figure>')
            else:
                images.append(f'<figure><img src="{html.escape(relative)}" alt="{html.escape(LABELS.get(key, key))}"><figcaption>{html.escape(LABELS.get(key, key))}</figcaption></figure>')
        duration = float(candidate.get("durationSeconds", 0) or 0)
        state_class = "approved" if candidate.get("status") == "APPROVED" else "review"
        cards.append(
            f'<article class="candidate {state_class}"><header><h2>{html.escape(candidate_id)}</h2>'
            f'<span>{html.escape(str(candidate.get("status", "REVIEW")))}</span></header>'
            f'<div class="images">{"".join(images)}</div>'
            f'<dl><dt>对应口播</dt><dd>{html.escape(str(candidate.get("narrationCue", "")))}</dd>'
            f'<dt>人物动作</dt><dd>{html.escape(str(candidate.get("actorAction", "")))}</dd>'
            f'<dt>视线目标</dt><dd>{html.escape(str(candidate.get("gazeTarget", "")))}</dd>'
            f'<dt>道具状态</dt><dd>{html.escape(str(candidate.get("propState", "")))}</dd>'
            f'<dt>显示时长</dt><dd>{duration:g} 秒</dd></dl></article>'
        )

    issues = "".join(f"<li>{html.escape(x)}</li>" for x in errors)
    cautions = "".join(f"<li>{html.escape(x)}</li>" for x in warnings)
    document = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>A-roll 审核</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#252b31;color:#fff7ec;font:18px/1.5 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{max-width:1700px;margin:auto;padding:36px}}h1{{font-size:42px}}.summary,.candidate{{background:#394149;border:1px solid #71818e;border-radius:20px;padding:24px;margin:20px 0}}.error{{color:#ff9f9f}}.warning{{color:#ffd36a}}header{{display:flex;justify-content:space-between;align-items:center}}header span{{padding:7px 13px;border-radius:999px;background:#e9a51a;color:#252b31;font-weight:800}}.approved header span{{background:#55d4b4}}.images{{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:14px}}figure{{margin:0;background:#252b31;border-radius:14px;overflow:hidden}}figure>img{{display:block;width:100%;height:300px;object-fit:contain;background:#f8f7f6}}.missing-frame{{height:300px;display:grid;place-items:center;color:#ff9f9f}}.aroll-paper{{position:relative;aspect-ratio:16/9;background:#f8f7f6;padding:6.5% 4% 18.5%}}.aroll-stage{{height:100%;border:2px solid #2d3137;border-radius:18px;overflow:hidden;background:#fdfaf4;box-shadow:0 8px 20px #0002}}.aroll-stage img{{display:block;width:100%;height:100%;object-fit:cover}}.subtitle-safe{{position:absolute;left:4%;right:4%;bottom:3%;height:14%;border:1px dashed #e9a51a;color:#2d3137;display:grid;place-items:center;font-size:13px}}figcaption{{padding:10px 14px;text-align:center}}dl{{display:grid;grid-template-columns:120px 1fr;gap:8px 16px}}dt{{color:#55d4b4}}dd{{margin:0}}@media(max-width:900px){{.images{{grid-template-columns:1fr 1fr}}}}</style></head>
<body><main><h1>{html.escape(str(data.get("projectId", "")))} · A-roll 审核</h1>
<section class="summary"><p>审核顺序：完整画面 → 面部 → 画面左眼 → 画面右眼 → 动作与时长。</p>
<ul class="error">{issues or '<li>没有阻断项</li>'}</ul><ul class="warning">{cautions}</ul></section>
{"".join(cards)}</main></body></html>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    print(f"已生成 A-roll 审核页：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
