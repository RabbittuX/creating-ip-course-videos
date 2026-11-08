# Gated chapter production

This workflow is serial across approval stages and may be parallel only inside the active stage.

```text
ENVIRONMENT_CAST_APPROVED
→ visual-outline approval
→ chapter-ordered A-roll generation/approval
→ audio alignment
→ B-roll + captions + preview
→ preview approval
→ render/QC/delivery
```

## Safe concurrency

- After `AROLL_IMAGES_APPROVED`, chapter TTS jobs may run concurrently because narration is fixed.
- While audio is being produced, static B-roll layout code may be prepared from the approved design, but state timing must wait for word alignment.
- B-roll timing, captions, and preview assembly may run per chapter after its `AUDIO_READY`; final preview waits for every chapter's `BROLL_SYNC_READY`.
- A-roll image generation is serial by chapter and action chain so each approved image can anchor the next one.

Use isolated chapter work orders, `contextPolicy: isolated`, and chapter-only write roots. Shared registries, presets, approvals, and final outputs remain coordinator-owned. Use cache hashes and `incremental_validate.py` for revisions; never rebuild unaffected approved chapters.
