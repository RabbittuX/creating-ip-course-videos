#!/usr/bin/env python3
"""Configure the skill with the user's own IP character and TTS settings.

  python3 scripts/setup_config.py --init     # write a config.json template
  python3 scripts/setup_config.py            # copy images, build registry, check

Files are written under $IP_COURSE_HOME (default ~/.config/ip-course-videos):
  config.json                         your settings (no credentials)
  ip-reference/<slot>.png             resolved template images
  character-reference/registry.json   hash-locked character registry
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import user_config as uc


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expand(value):
    return Path(value).expanduser() if value else None


def init():
    target = uc.config_path()
    if target.exists():
        print(f"已存在，未覆盖：{target}")
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(uc.SKILL_ROOT / "config.example.json", target)
    print(f"已生成配置模板：{target}\n填好角色图路径、外观特征和音色后，再运行一次本脚本（不带 --init）。")
    return 0


def apply():
    cfg = uc.load_config()
    if not cfg:
        print(f"错误：找不到 {uc.config_path()}，先运行 --init", file=sys.stderr)
        return 2
    errors = []
    host = cfg.get("host") or {}
    images = {}
    for key, value in (host.get("images") or {}).items():
        if value:
            images[key] = expand(value)
    for extra in cfg.get("extraCharacters") or []:
        for key, value in (extra.get("images") or {}).items():
            if value:
                images[key] = expand(value)
    for key, path in images.items():
        if not path.is_file():
            errors.append(f"图片不存在：{key} -> {path}")
    if "host-front" not in images:
        errors.append("host.images.host-front 必填（IP 人物正面定稿图）")
    invariants = [x for x in host.get("identityInvariants") or [] if x and not x.startswith(("用 3", "例如"))]
    if not invariants:
        errors.append("host.identityInvariants 至少填写一条真实的外观特征")
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 2

    slot_dir = uc.user_slot_dir()
    if slot_dir.exists():
        shutil.rmtree(slot_dir)
    uc.materialize_slots(slot_dir, images)

    host_id = host.get("characterId", "ip-host")
    characters = [{
        "characterId": host_id,
        "displayName": host.get("displayName", "IP 人物"),
        "role": "required-host",
        "status": "approved",
        "version": host.get("version", "1.0.0"),
        "canonicalPath": "../ip-reference/host-front.png",
        "sha256": sha256(slot_dir / "host-front.png"),
        "identityInvariants": invariants,
        "poseReferences": [f"../ip-reference/{k}.png" for k in sorted(images) if k.startswith("host-") and k != "host-front"],
    }]
    for extra in cfg.get("extraCharacters") or []:
        slot = extra.get("slot") or extra.get("characterId")
        if slot not in images:
            continue
        extra_invariants = [x for x in extra.get("identityInvariants") or [] if x and not x.startswith("填写")]
        if not extra_invariants:
            print(f"错误：{extra.get('characterId')} 配置了图片但没有填写 identityInvariants", file=sys.stderr)
            return 2
        characters.append({
            "characterId": extra["characterId"],
            "displayName": extra.get("displayName", extra["characterId"]),
            "role": extra.get("role", "optional"),
            "status": "approved",
            "version": extra.get("version", "1.0.0"),
            "canonicalPath": f"../ip-reference/{slot}.png",
            "sha256": sha256(slot_dir / f"{slot}.png"),
            "identityInvariants": extra_invariants,
        })
    registry = {
        "schemaVersion": 1,
        "referenceRoot": "character-reference",
        "policy": {
            "attachApprovedReferencesForEveryCastMember": True,
            "blockMissingRequiredCharacter": True,
            "allowSceneFramesAsCanonicalReferences": False,
            "requireHashMatch": True,
        },
        "characters": characters,
    }
    path = uc.user_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    from validate_character_registry import validate
    problems = validate(path)
    if problems:
        for problem in problems:
            print(f"错误：{problem}", file=sys.stderr)
        return 2

    tts = cfg.get("tts") or {}
    print(f"角色登记表已生成：{path}（{len(characters)} 个角色）")
    print(f"模板图片已就位：{slot_dir}")
    if not tts.get("voiceType") or "填你" in str(tts.get("voiceType")):
        print("提醒：tts.voiceType 还没填，配音前需要填写")
    missing = [name for name in ("DOUBAO_APPID", "DOUBAO_TOKEN") if not os.environ.get(name)]
    if missing:
        print(f"提醒：未检测到环境变量 {', '.join(missing)}（密钥只从环境变量读取，不写入配置）")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true", help="write a config.json template")
    args = parser.parse_args()
    return init() if args.init else apply()


if __name__ == "__main__":
    raise SystemExit(main())
