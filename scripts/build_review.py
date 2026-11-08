#!/usr/bin/env python3
"""Build a static human-review dashboard from a project manifest."""

import argparse
import html
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    project_path = Path(args.project)
    data = json.loads(project_path.read_text(encoding="utf-8"))
    rows = "".join(
        f"<tr><td>{html.escape(str(ch.get('id')))}</td><td>{html.escape(str(ch.get('state', 'DRAFT')))}</td><td>{html.escape(str(ch.get('previewBuildId') or '—'))}</td><td>{html.escape(str(ch.get('approvedBuildId') or '—'))}</td></tr>"
        for ch in data.get("chapters", [])
    )
    identity = ""
    registry_value = data.get("characterRegistry")
    if registry_value:
        registry_path = Path(registry_value)
        if not registry_path.is_absolute():
            registry_path = project_path.parent / registry_path
        if registry_path.is_file():
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            host = next((c for c in registry.get("characters", []) if c.get("role") == "required-host"), {})
            identity = "".join(f"<li>{html.escape(str(item))}</li>" for item in host.get("identityInvariants", []))
    document = f"""<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><title>课程视频人工审阅</title><style>body{{font:18px/1.6 -apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;background:#252b31;color:#fff7ec;margin:0;padding:48px}}main{{max-width:1280px;margin:auto}}section{{background:#394149;border:1px solid #71818e;border-radius:20px;padding:28px;margin:22px 0}}h1{{font-size:42px}}h2{{color:#e9a51a}}li{{margin:8px 0}}table{{width:100%;border-collapse:collapse}}td,th{{padding:14px;border-bottom:1px solid #71818e;text-align:left}}code{{color:#55d4b4}}</style><main><h1>{html.escape(str(data.get('projectId')))} · 人工审阅</h1><section><h2>固定开头 A-roll</h2><ul><li><code>opening-title</code>：只核对当期标题，底图、人物与动作不得变化</li><li><code>opening-transition</code>：零可变字段，直接复用开场过渡画面</li><li>两套模板都不进入 Image 2.0，只检查挂载位置和最终预览</li></ul></section><section><h2>IP 人物身份检查</h2><ul>{identity}<li>按画面左右核对，与定稿图一致</li><li>失败时重新生成整张图，禁止只做局部修补</li></ul></section><section><h2>审批状态</h2><table><thead><tr><th>章节</th><th>状态</th><th>预览 build ID</th><th>批准 build ID</th></tr></thead><tbody>{rows}</tbody></table></section><section><h2>STOP 规则</h2><p>A-roll、B-roll、浏览器预览任一阶段未获人工批准，不得进入下一阶段。</p></section></main></html>"""
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(document, encoding="utf-8")
    print(f"已生成审阅页：{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
