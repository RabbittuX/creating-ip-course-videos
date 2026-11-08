#!/usr/bin/env python3
"""Reject preview assemblies that bypass the locked A-roll and B-roll systems."""

import argparse
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
FIXED_AROLL = {
    "opening-title": SKILL_ROOT / "assets" / "arroll" / "fixed" / "opening-title.html",
    "opening-transition": SKILL_ROOT / "assets" / "arroll" / "fixed" / "opening-transition.html",
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve(base, value):
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


class StructureParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens = []
        self.ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"style", "script"}:
            self.ignored_depth += 1
            return
        if self.ignored_depth:
            return
        kept = []
        for key, value in attrs:
            if key in {"id", "style", "src", "href"}:
                continue
            if key == "class":
                kept.append((key, " ".join(sorted((value or "").split()))))
            elif key.startswith("data-") and key not in {"data-composition-id", "data-duration"}:
                kept.append((key, value or ""))
        self.tokens.append(("start", tag, tuple(sorted(kept))))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.tokens.append(("end", tag))

    def handle_endtag(self, tag):
        if tag in {"style", "script"} and self.ignored_depth:
            self.ignored_depth -= 1
            return
        if self.ignored_depth:
            return
        self.tokens.append(("end", tag))


def structural_fingerprint(path):
    parser = StructureParser()
    parser.feed(Path(path).read_text(encoding="utf-8"))
    payload = json.dumps(parser.tokens, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate(manifest_path):
    manifest_path = Path(manifest_path).resolve()
    base = manifest_path.parent
    errors = []
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"无法读取 visual assembly：{exc}"]
    if data.get("status") != "READY":
        errors.append("visual assembly 尚未标记为 READY")

    fixed = {item.get("role"): item for item in data.get("fixedAroll", [])}
    for role, expected in FIXED_AROLL.items():
        item = fixed.get(role)
        actual = resolve(base, item.get("sourcePath")) if item and item.get("sourcePath") else None
        if not actual or not actual.is_file() or actual != expected.resolve() or digest(actual) != digest(expected):
            errors.append(f"固定 A-roll {role} 必须直接使用 skill 锁定源文件，不能自制替代")

    for item in data.get("arollScenes", []):
        label = f"A-roll {item.get('sceneId', '<missing>')}"
        value = item.get("compositionPath")
        path = resolve(base, value) if value else None
        if not path or not path.is_file():
            errors.append(f"{label} 缺少组合文件")
            continue
        source = path.read_text(encoding="utf-8").lower()
        required = {
            "data-aroll-paper": "纸张外壳 data-aroll-paper",
            "data-aroll-stage": "内舞台 data-aroll-stage",
            "data-aroll-artwork": "舞台内画面 data-aroll-artwork",
            "#f8f7f6": "外层背景 #f8f7f6",
            "#fdfaf4": "舞台背景 #fdfaf4",
            "left:72px": "舞台左边距 72px",
            "right:72px": "舞台右边距 72px",
            "top:70px": "舞台上边距 70px",
            "height:820px": "舞台高度 820px",
        }
        for token, description in required.items():
            if token not in re.sub(r"\s+", "", source) if token.endswith("px") else token not in source:
                errors.append(f"{label} 未使用锁定 A-roll 纸张外壳：缺少{description}")
        if "background:#252b31" in re.sub(r"\s+", "", source) or "inset:-18px" in re.sub(r"\s+", "", source):
            errors.append(f"{label} 仍是错误的深色全屏画面，不得把审核图直接铺满根画布")

    for item in data.get("brollScenes", []):
        if item.get("designOrigin") != "template":
            errors.append(f"B-roll {item.get('sceneId', '<missing>')} 未声明来自注册模板")
            continue
        label = f"B-roll {item.get('sceneId', '<missing>')}"
        template_value, composition_value = item.get("templateSourcePath"), item.get("compositionPath")
        template = resolve(base, template_value) if template_value else None
        composition = resolve(base, composition_value) if composition_value else None
        if not template or not template.is_file() or not composition or not composition.is_file():
            errors.append(f"{label} 缺少模板源文件或实例文件")
            continue
        if item.get("templateSourceHash") != digest(template):
            errors.append(f"{label} 模板来源哈希不匹配")
        if structural_fingerprint(template) != structural_fingerprint(composition):
            errors.append(f"{label} 未保留注册模板结构，禁止用统一通用面板冒充模板")

    evidence = {"manifestPath": str(manifest_path), "manifestHash": digest(manifest_path),
                "arollCount": len(data.get("arollScenes", [])), "brollCount": len(data.get("brollScenes", []))}
    return evidence, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    evidence, errors = validate(args.manifest)
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2
    print(json.dumps(evidence, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
