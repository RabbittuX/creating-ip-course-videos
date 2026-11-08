---
name: creating-ip-course-videos
description: Use when making a branded long-form narrated course or explainer video keeping the user's configured IP character consistent through review-gated A-roll, B-roll, subtitles, voice, and delivery.
---

# Creating IP Course Videos

Build HyperFrames chapters through whole-video approval barriers. Use Image 2.0/2.5 only for generated A-roll and `ffmpeg` for media checks.

Placeholder IP? **STOP**: [user-setup.md](references/user-setup.md).

## Required order

Read [workflow.md](references/workflow.md). **First audit the 口播稿** via [douyin-content-preflight.md](references/douyin-content-preflight.md); resolve off-platform viewer directions without silently changing locked narration. Then initialize, preserve headings, and index with `index_narration.py`. `planning/narration-manifest.json` is the spoken-text source. Give each audience-facing second-level heading one silent fixed-template B-roll; read [secondary-title-system.md](references/secondary-title-system.md).

1. Plan whole-video backgrounds/cast using approved references; build one concise review, then **STOP** until every chapter is `ENVIRONMENT_CAST_APPROVED`. Read [character-reference-system.md](references/character-reference-system.md).
2. Make a gap-free A/B outline with exact character spans, ratios, B-roll previews, `progressMode`, and source text. Recheck viewer-facing text and visual cues under [douyin-content-preflight.md](references/douyin-content-preflight.md). Build one review, then **STOP** until every chapter is `VISUAL_OUTLINE_APPROVED`; run `prepare_broll_sync.py`. Read [planning-review-system.md](references/planning-review-system.md).
3. Generate A-roll 按章节串行. 固定 A-roll `opening-title`/`opening-transition` 不使用 Image 2.0; read [fixed-aroll-system.md](references/fixed-aroll-system.md). Quarantine candidates, run `validate_aroll.py` and `build_aroll_review.py`, then **STOP**. Promote exact approved IDs with `promote_aroll.py` into `assets/arroll/approved`; audio waits for all chapters to reach `AROLL_IMAGES_APPROVED`.
4. Generate TTS/alignment from narration via `tts_doubao.py`. `AUDIO_READY` runs `build_actual_duration_report.py`; drift over 1 second or ratio drift over 5 points invalidates approval. Run `segment_captions.py`, `validate_captions.py`, B-roll mapping/wiring, and insert all source-script secondary titles from the one fixed subchapter template as silent timeline intervals. Run `validate_full_timeline.py`, verify secondary-title count/order/boundaries against the source heading ledger, and **then run `validate_visual_assembly.py`** before creating one hash-bound `preview/preview-ready.json`. Every B-roll needs an approved candidate and composition hash. `project.json` must bind `visualAssembly`, and `preview-ready.json` must bind its current hash. After all chapters reach `BROLL_SYNC_READY`/`PREVIEW_READY`, **STOP** for full-video preview review. Read the routed audio, subtitle, and B-roll references in [workflow.md](references/workflow.md).
5. Render only `PREVIEW_APPROVED`. `DELIVERY_READY` requires `renders/final/delivery-ready.json` covering all chapters, timeline, master, upload, and loudness evidence. Read [final-qc.md](references/final-qc.md) and [delivery-profiles.md](references/delivery-profiles.md).

Before B-roll implementation run `audit_broll_backgrounds.py`. Use `validate_broll.py`, `build_broll_review.py`, and `promote_broll.py`; `broll-runtime-inspector.js` is diagnostic only. The preview assembly hard gate is defined in [visual-assembly-gate.md](references/visual-assembly-gate.md); it is mandatory and non-bypassable.

Record effects, speed, audio replacements, and exceptions in `planning/creative-directives.json`; changes invalidate preview.

## A-roll review boundary

`validate_aroll.py` performs structural checks only: file/hash/path, dimensions when supplied, IDs, action-chain fields, duration, and approval provenance. It must not judge eyes, hands, identity similarity, background continuity, or visual quality. Show those details to the user in `build_aroll_review.py`; human approval is authoritative.

## B-roll state invariant

Never evenly space progress items. Resolve stored character offsets against word alignment. The shared controller renders current yellow, completed green, unvisited gray, and moves/hides the IP pointer. Narration-driven scenes require embedded `BrollProgressController.bindGsap`; a configured path is not evidence. Check only files, order, increasing times, and runtime marker—no AI visual inspection or per-trigger screenshots.

## Iteration

Use isolated chapter-local work orders, cache hashes, and `incremental_validate.py` after a gate opens. Concurrency is allowed only inside the currently approved stage; A-roll chapter image generation itself remains serial. Never regenerate approved unrelated work or edit approvals by hand. Read [approval-gates.md](references/approval-gates.md) and [parallel-production.md](references/parallel-production.md).

Run the `skill-creator` quick validator and `node --test tests/*.test.mjs` before completion.
