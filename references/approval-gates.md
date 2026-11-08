# Approval gates

Use `scripts/approval_gate.py`; never edit approval JSON by hand.

## Required chain

```text
NARRATION_INDEXED
→ ENVIRONMENT_CAST_APPROVED
→ VISUAL_OUTLINE_APPROVED
→ AROLL_IMAGES_APPROVED
→ AUDIO_READY
→ BROLL_SYNC_READY
→ PREVIEW_READY
→ PREVIEW_APPROVED
→ RENDERED
→ FINAL_QC_PASSED
→ DELIVERY_READY
```

The gate name is `aroll-images`; the milestone token is `AROLL_IMAGES_APPROVED`. Environment/cast, outline, A-roll, preview, and delivery are whole-video barriers: no chapter may advance while another chapter is missing the prior global stage.

## Commands

- Human gates: `request/approve --gate environment-cast|visual-outline|aroll-images|preview`.
- Deterministic milestones: `mark-ready --milestone audio|broll-sync|preview-ready|rendered|final-qc|delivery`.
- `audio`, `broll-sync`, `preview-ready`, `rendered`, `final-qc`, and `delivery` require `--project-root <project>`. They validate and record current file hashes; a build ID alone cannot bypass missing or stale artifacts.
- `preview-ready` requires `preview/preview-ready.json` bound to the current composition, full parent timeline, creative directives, and B-roll manifest. It must contain every project chapter in order.
- `delivery` requires chapter `render-ready.json`/`final-qc.json` evidence plus the aggregate `renders/final/delivery-ready.json` and a passing full-video loudness report.
- Every request and approval uses an exact build ID. A different build is unapproved.

Stop after each of the first three human reviews and after preview review. Feedback authorizes only the requested revision, never silent substitution.

## Invalidation

Invalidate from the earliest changed token across every chapter. A character/background change invalidates the visual outline and every downstream artifact. An A-roll image change invalidates audio only when narration or timing also changed, otherwise invalidate from `AROLL_IMAGES_APPROVED`. Audio replacement or speed changes invalidate actual-duration evidence, B-roll timing, captions, preview, and render. Any creative-directive, B-roll manifest, preview composition, or media change invalidates preview approval and render evidence.
