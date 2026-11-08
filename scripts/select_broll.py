#!/usr/bin/env python3
"""Deterministically select and lock B-roll templates for a course plan."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


FIXED_KIND_TO_ROLE = {"chapter": "chapter", "subchapter": "subchapter", "prompt-input": "prompt-input"}


def stable_rank(seed: str, template_id: str) -> str:
    return hashlib.sha256(f"{seed}/{template_id}".encode("utf-8")).hexdigest()


def compatible(template, scene):
    item_count = int(scene.get("itemCount", 0) or 0)
    duration = scene.get("durationSeconds")
    required = set(scene.get("requiredInteractions", []))
    if template.get("progressMode") != scene.get("progressMode"):
        return False
    if item_count and not (
        int(template.get("minItems", 0)) <= item_count <= int(template.get("maxItems", 999))
    ):
        return False
    if duration is not None and not (
        float(template.get("minDurationSeconds", 0))
        <= float(duration)
        <= float(template.get("maxDurationSeconds", 1e9))
    ):
        return False
    if not required.issubset(set(template.get("supportedInteractions", []))):
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    project = json.loads(Path(args.project).read_text(encoding="utf-8"))
    registry = json.loads(Path(args.registry).read_text(encoding="utf-8"))
    templates = registry["templates"]
    fixed = {item["role"]: item for item in templates if item.get("mode") == "fixed" and item.get("enabled", True)}
    library = [item for item in templates if item.get("mode") == "library" and item.get("enabled", True)]
    usage = Counter()
    recent_functional = []
    selections = []

    for scene in project.get("scenes", []):
        scene_id = str(scene["id"])
        chapter_id = str(scene.get("chapterId", ""))
        kind = scene.get("kind", "template")
        if kind in FIXED_KIND_TO_ROLE:
            chosen = fixed[FIXED_KIND_TO_ROLE[kind]]
            reason = "唯一固定模板，绕过模板库选择"
        else:
            if scene.get("progressMode") not in {"static", "narration-driven"}:
                raise SystemExit(f"场景 {scene_id} 必须声明 progressMode: static|narration-driven")
            family = scene.get("family")
            tags = set(scene.get("tags", []))
            candidates = [x for x in library if (not family or x.get("family") == family)]
            candidates = [x for x in candidates if compatible(x, scene)]
            if not candidates:
                raise SystemExit(
                    f"场景 {scene_id} 没有兼容模板：family={family}, "
                    f"itemCount={scene.get('itemCount')}, duration={scene.get('durationSeconds')}, "
                    f"required interaction={scene.get('requiredInteractions', [])}"
                )
            eligible_ids = [x["id"] for x in candidates]
            blocked = set(recent_functional[-3:])
            spaced = [x for x in candidates if x["id"] not in blocked]
            if spaced:
                candidates = spaced
            min_used = min(usage[x["id"]] for x in candidates)
            candidates = [x for x in candidates if usage[x["id"]] == min_used]
            max_overlap = max(len(tags & set(x.get("tags", []))) for x in candidates)
            if max_overlap:
                candidates = [x for x in candidates if len(tags & set(x.get("tags", []))) == max_overlap]
            seed = f"{project.get('projectId', '')}/{chapter_id}/{scene_id}"
            chosen = min(candidates, key=lambda x: stable_rank(seed, x["id"]))
            usage[chosen["id"]] += 1
            recent_functional.append(chosen["id"])
            reason = "先校验容量、时长与交互，再执行三场景间隔、语义匹配和整片均衡"

        selections.append({
            "sceneId": scene_id,
            "chapterId": chapter_id,
            "templateId": chosen["id"],
            "source": chosen["source"],
            "mode": chosen["mode"],
            "reason": reason,
            "eligibleTemplateIds": eligible_ids if kind not in FIXED_KIND_TO_ROLE else [chosen["id"]],
            "durationSeconds": scene.get("durationSeconds"),
            "requiredInteractions": scene.get("requiredInteractions", []),
            "progressMode": chosen.get("progressMode"),
        })

    warnings = []
    functional = [x for x in selections if x["mode"] == "library"]
    family_uses = Counter()
    template_uses = Counter()
    family_variants = {}
    by_id = {x["id"]: x for x in templates}
    for item in functional:
        family = by_id[item["templateId"]].get("family")
        family_uses[family] += 1
        template_uses[(family, item["templateId"])] += 1
        family_variants.setdefault(family, set()).update(
            by_id[x].get("id") for x in item["eligibleTemplateIds"] if by_id.get(x, {}).get("family") == family
        )
    for (family, template_id), count in template_uses.items():
        total = family_uses[family]
        if len(family_variants.get(family, set())) >= 3 and count / total > 0.4:
            warnings.append(f"{family}/{template_id} 占比 {count / total:.0%} 超过 40%")
    output = {"schemaVersion": 2, "projectId": project.get("projectId"), "selections": selections, "warnings": warnings}
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已锁定 {len(selections)} 个 B-roll 选择：{target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
