# Workflow

## Inputs

Require the complete narration, chapter boundaries, project title, output location, and any real UI media. Read all narration before assigning visuals. Stable chapter/scene IDs and narration character spans are fixed before production; audio timestamps do not exist until approved A-roll planning is complete.

## Opening narration preflight

Before `init_project.py` or `index_narration.py`, review the complete source 口播稿 under [douyin-content-preflight.md](douyin-content-preflight.md). Give the creator a concise pass/findings report with exact excerpts and proposed minimal rewrites. Resolve explicit off-platform calls to action before production. If the source is locked, do not change it without the creator's direction; pause downstream work on the affected script. This review is contextual and does not claim to certify platform approval. Repeat the check for audience-facing text and visual cues when reviewing the visual outline.

## Sequential stages

1. **Narration and structure:** after the opening preflight, preserve the complete source script and record its heading hierarchy in `planning/heading-ledger.json` before stripping Markdown for TTS. Write spoken chapter text into `planning/narration-manifest.json` with `index_narration.py`. This immutable text/hash pair is the only spoken-text source downstream; the heading ledger is the source for non-spoken title cards. Follow [secondary-title-system.md](secondary-title-system.md).
2. **Environment/cast:** plan backgrounds, approved characters, and continuous actions; stop for `ENVIRONMENT_CAST_APPROVED`.
3. **Visual outline:** split A/B-roll, keep summaries concise, attach exact narration ranges, planned durations/ratios, template/custom previews, and an explicit B-roll `progressMode`. Include every audience-facing second-level heading as a separate fixed-template B-roll with zero narration characters; stop for `VISUAL_OUTLINE_APPROVED`, then run `prepare_broll_sync.py` to persist narration mappings.
4. **A-roll images:** generate chapter by chapter, serially inside each action chain; quarantine, structurally validate, show in the final screen shell, stop for `AROLL_IMAGES_APPROVED`, then promote every exact approved candidate. Audio cannot start while any candidate remains outside `approvedRoot`.
5. **Audio and alignment:** produce one chapter TTS request from the canonical narration, normalize it, create word-level alignment, and generate `planning/actual-duration-report.json`. Drift beyond the locked thresholds returns the project to outline review.
6. **B-roll/captions/preview:** derive B-roll state times from narration maps, wire narration-driven compositions, bind all B-roll compositions to approved candidates, build semantic captions, instantiate every required secondary title from `assets/broll/fixed/subchapter.html`, and run `build_full_timeline.py`. Check that title count/order/text/boundaries equal `planning/heading-ledger.json`, that no narration or captions play during title holds, and that title holds do not overlap other A/B-roll. Then write `planning/visual-assembly.json` and pass `validate_visual_assembly.py`. Write one `preview/preview-ready.json` with composition, timeline, creative-directive, B-roll-manifest, heading-ledger, and visual-assembly hashes; record all chapters as `BROLL_SYNC_READY`/`PREVIEW_READY`, then stop. The validator must prove locked A-roll shell usage, exact fixed-role sources, and registered-template B-roll structural provenance.
7. **Render/delivery:** render only the exact `PREVIEW_APPROVED` build. Keep chapter render/QC manifests, then create the aggregate `renders/final/delivery-ready.json` covering every chapter plus full-video master, upload file, parent timeline, and loudness report.

Concurrency is permitted only inside the currently open stage and never to bypass a human stop. The A-roll image sequence remains serial by chapter.

## Source-of-truth files

- `planning/environment-cast-plan.json`: chapter backgrounds, cast versions, and action chains.
- `planning/narration-manifest.json`: canonical chapter narration and hashes; all downstream text must match.
- `planning/heading-ledger.json`: source-script heading hierarchy, audience-facing secondary titles, editorial-heading exclusions, and source hash.
- `planning/visual-outline.json`: concise A/B design, narration spans, design origin, previews, and planned/actual ratios.
- `planning/creative-directives.json`: project-only effects, speed changes, and exceptions.
- `assets/character-reference/registry.json`: canonical cast identities and hashes.
- `planning/aroll-manifest.json`: quarantined candidates and exact human approvals.
- `chapters/<id>/planning/broll-narration-map.json`: summary-item to narration-span mapping.
- `chapters/<id>/timing/broll-state-timeline.json`: word-aligned active/completed state times.
- `chapters/<id>/timing/captions.json`: semantic cues, narration/alignment/audio hashes, source spans, and word-aligned times.
- `timing/full-timeline.json`: absolute chapter/title/sting/narration/caption windows used by the preview gate.
- `preview/preview-ready.json`: one whole-video reviewed build bound to composition, parent timeline, creative directives, and B-roll manifest.
- `renders/<id>/{render-ready,final-qc}.json`: chapter render/QC provenance.
- `renders/final/delivery-ready.json`: aggregate full-video delivery provenance and loudness evidence.
- `approvals.json`: authoritative gate/build evidence.
- `project.json`: captions, media, preview/render IDs, and QC results.

Do not infer approval from silence, a prior chapter, or approval of a different artifact.
