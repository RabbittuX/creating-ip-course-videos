#!/usr/bin/env python3
"""Apply the locked B-roll canvas treatment to every local template and component."""

import argparse
import hashlib
import re
from pathlib import Path


THEME_ID = "locked-grid-v1"
THEME_BLOCK = '''  <style data-broll-theme="locked-grid-v1">
    [data-broll-theme-root="locked-grid-v1"]{background-color:#252b31!important;color:#fff7ec!important;font-family:"PingFang SC","Microsoft YaHei",sans-serif!important}
    [data-broll-theme-root="locked-grid-v1"]>.broll-background{position:absolute;inset:0;z-index:0;pointer-events:none;background-color:#252b31;background-image:radial-gradient(circle at 50% 0%,rgba(78,95,109,.18),transparent 60%),linear-gradient(rgba(132,153,171,.10) 1px,transparent 1px),linear-gradient(90deg,rgba(132,153,171,.10) 1px,transparent 1px);background-size:auto,44px 44px,44px 44px;background-position:0 0,0 0,0 0}
    [data-broll-theme-root="locked-grid-v1"]>:is(.paper,.grid,.texture){display:none!important}
    [data-broll-theme-root="locked-grid-v1"]>.title,[data-broll-theme-root="locked-grid-v1"]>h1,[data-broll-theme-root="locked-grid-v1"]>h2{color:#fff7ec!important}
    [data-broll-theme-root="locked-grid-v1"]>.title em,[data-broll-theme-root="locked-grid-v1"]>h1 em,[data-broll-theme-root="locked-grid-v1"]>h2 em{color:#e9a51a!important}
    [data-broll-theme-root="locked-grid-v1"]>:is(.tag,.step){background:#394149!important;border-color:#71818e!important;color:#fff7ec!important}
  </style>
'''


def discover(root: Path):
    return sorted(
        list((root / "fixed").glob("*.html"))
        + list((root / "library" / "templates").glob("*.html"))
        + list((root / "library" / "components").glob("*.html"))
    )


def normalize(path: Path):
    source = path.read_text(encoding="utf-8")
    source = re.sub(
        r'<style data-broll-theme="locked-grid-v1">.*?</style>',
        "",
        source,
        flags=re.DOTALL,
    )
    source = re.sub(
        r'\n\s*<div[^>]*class="broll-background"[^>]*data-broll-background="locked-grid-v1"[^>]*></div>',
        "",
        source,
    )
    root_match = re.search(r'<div\b(?=[^>]*\bdata-composition-id="[^"]+")[^>]*>', source)
    if not root_match:
        raise ValueError(f"{path} 缺少 composition root")
    root_tag = root_match.group(0)
    root_tag = re.sub(r'\sdata-broll-theme-root="[^"]*"', "", root_tag)
    root_tag = root_tag[:-1] + f' data-broll-theme-root="{THEME_ID}">'
    marker = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:8]
    background = (
        f'\n    <div data-hf-id="hf-bg-{marker}" class="broll-background" '
        f'data-broll-background="{THEME_ID}"></div>'
    )
    replacement = root_tag + background
    source = source[:root_match.start()] + replacement + source[root_match.end():]
    closing = source.lower().rfind("</template>")
    if closing < 0:
        closing = source.lower().rfind("</body>")
    if closing < 0:
        raise ValueError(f"{path} 缺少 template/body 结束标签")
    return source[:closing].rstrip() + "\n" + THEME_BLOCK + source[closing:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="assets/broll directory")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = Path(args.root)
    files = discover(root)
    changed = []
    for path in files:
        updated = normalize(path)
        current = path.read_text(encoding="utf-8")
        if updated != current:
            changed.append(path)
            if args.write:
                path.write_text(updated, encoding="utf-8")
    verb = "已统一" if args.write else "需要统一"
    print(f"{verb} {len(changed)}/{len(files)} 个 B-roll 文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
