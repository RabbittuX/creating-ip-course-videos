#!/usr/bin/env python3
"""Locate and merge the user's private configuration.

Everything personal (IP character images, identity description, TTS voice,
speech rate, loudness targets, brand text) lives OUTSIDE the skill directory so
the skill can be shared and updated without leaking or overwriting it.

Lookup order for the config home:
  1. $IP_COURSE_HOME
  2. ~/.config/ip-course-videos

Credentials are never stored here; TTS keys come only from environment
variables (see references/tts-caption-audio.md).
"""

import copy
import json
import os
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
PRESETS = SKILL_ROOT / "assets" / "presets"
EXAMPLE_REGISTRY = SKILL_ROOT / "assets" / "character-reference" / "registry.json"
SLOTS_FILE = SKILL_ROOT / "assets" / "character-slots.json"


def config_home():
    value = os.environ.get("IP_COURSE_HOME")
    return Path(value).expanduser() if value else Path.home() / ".config" / "ip-course-videos"


def config_path():
    return config_home() / "config.json"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_config():
    path = config_path()
    return load_json(path) if path.is_file() else {}


def is_configured():
    return config_path().is_file() and user_registry_path().is_file()


def _merge(base, override):
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        elif value is not None:
            result[key] = value
    return result


def audio_profile():
    """Skill defaults merged with the user's tts/loudness settings."""
    profile = load_json(PRESETS / "audio-profile.json")
    cfg = load_config()
    if cfg.get("tts"):
        profile["tts"] = _merge(profile.get("tts", {}), cfg["tts"])
    if cfg.get("loudness"):
        profile["loudness"] = _merge(profile.get("loudness", {}), cfg["loudness"])
    return profile


def brand():
    return _merge({"courseTitle": "从入门到精通", "appName": "AI 助手"}, load_config().get("brand"))


def slots():
    return load_json(SLOTS_FILE)


def user_registry_path():
    return config_home() / "character-reference" / "registry.json"


def user_slot_dir():
    return config_home() / "ip-reference"


def character_registry_path():
    """User registry when configured, otherwise the bundled example."""
    path = user_registry_path()
    return path if path.is_file() else EXAMPLE_REGISTRY


def slot_source_dir():
    """Directory holding the resolved slot images used by templates."""
    path = user_slot_dir()
    return path if path.is_dir() else SKILL_ROOT / "assets" / "ip-reference"


def materialize_slots(target_dir, provided=None):
    """Write every template slot to target_dir/<slot>.png, following fallbacks.

    `provided` maps slot -> image path. When omitted, images already present in
    slot_source_dir() are used. Returns {slot: source path actually used}.
    """
    import shutil

    if provided is None:
        source = slot_source_dir()
        provided = {item["slot"]: source / f'{item["slot"]}.png' for item in slots()["slots"]}
    provided = {k: Path(v).expanduser() for k, v in provided.items() if v and Path(v).expanduser().is_file()}
    table = {item["slot"]: item for item in slots()["slots"]}
    transparent = SKILL_ROOT / "assets" / "ip-reference" / "transparent.png"

    def resolve(slot, seen=()):
        if slot in provided:
            return provided[slot]
        if slot == "transparent":
            return transparent
        fallback = table[slot].get("fallback")
        if not fallback or slot in seen:
            raise SystemExit(f"缺少必填角色图：{slot}（请在 config.json 里配置后重新运行 setup_config.py）")
        return resolve(fallback, seen + (slot,))

    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    used = {}
    for slot in table:
        src = resolve(slot)
        dst = target_dir / f"{slot}.png"
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        used[slot] = str(src)
    return used


def host_character_id():
    return load_config().get("host", {}).get("characterId", "ip-host")
