#!/usr/bin/env python3
"""Embed the shared progress controller and bind a resolved scene timeline to GSAP seek."""

import argparse
import json
import sys
from pathlib import Path


def insert_before(html, marker, payload):
    at = html.rfind(marker)
    if at < 0:
        return None
    return html[:at] + payload + "\n" + html[at:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--composition", required=True)
    parser.add_argument("--timeline", required=True)
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--origin-ms", type=int, default=0)
    parser.add_argument("--controller")
    args = parser.parse_args()
    composition = Path(args.composition)
    timeline = json.loads(Path(args.timeline).read_text(encoding="utf-8"))
    items = [item for item in timeline.get("items", []) if str(item.get("sceneId", args.scene_id)) == args.scene_id]
    if not items:
        print(f"错误：时间线中没有 sceneId={args.scene_id} 的项目", file=sys.stderr)
        return 2
    skill_root = Path(__file__).resolve().parent.parent
    controller_path = Path(args.controller) if args.controller else skill_root / "assets" / "broll" / "broll-progress-controller.js"
    controller = controller_path.read_text(encoding="utf-8")
    html = composition.read_text(encoding="utf-8")
    if "data-broll-progress-wired=" in html:
        print("错误：组合文件已经接入 B-roll progress runtime", file=sys.stderr)
        return 2
    encoded_items = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    binding = f'''<script data-broll-progress-controller="shared-v1">{controller}</script>
<script data-broll-progress-wired="{args.scene_id}">
(()=>{{
  const sceneId={json.dumps(args.scene_id, ensure_ascii=False)};
  const root=document.querySelector(`[data-composition-id="${{sceneId}}"]`);
  const timeline={encoded_items};
  const gsapTimeline=window.__timelines&&window.__timelines[sceneId];
  window.BrollProgressController.bindGsap(root,timeline,gsapTimeline,{{originMs:{args.origin_ms}}});
}})();
</script>'''
    updated = insert_before(html, "</template>", binding)
    if updated is None:
        updated = insert_before(html, "</body>", binding)
    if updated is None:
        updated = html + "\n" + binding + "\n"
    composition.write_text(updated, encoding="utf-8")
    print(f"已接入 B-roll 运行时：{args.scene_id}（{len(items)} 项）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
