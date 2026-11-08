# B-roll template system

## Fixed roles

`chapter`, `subchapter`, and `prompt-input` each have exactly one immutable template in `assets/broll/fixed/`. Use them directly; never query or randomly select an alternative. Only content fields and timing may change.

## Library roles

All other B-roll uses `assets/broll/template-registry.json`. Every enabled registry entry must declare `version`, `minItems`, `maxItems`, `minDurationSeconds`, `maxDurationSeconds`, `supportedInteractions`, and `progressMode: static|narration-driven`. Every planned functional scene must explicitly declare the same `progressMode`; selection never substitutes one mode for the other. Every planned scene must declare `durationSeconds` and `requiredInteractions` when either is constrained:

1. Filter enabled library entries by family, capacity, duration, required interaction, and semantic tags.
2. Semantic fit outranks novelty.
3. Prefer the least-used eligible template in the current video and chapter.
4. Put at least three other functional B-roll scenes between exact template repeats when another eligible variant exists.
5. Use the deterministic project/chapter/scene seed to break ties.
6. Save the result to `template-selection-lock.json`; preview and render must read the lock, not reselect.

`scripts/select_broll.py` executes these filters and saves the eligible set and decision reason in the lock. When a family has at least three eligible variants, `scripts/validate_broll.py` warns if one exceeds 40% of that family's uses. If only one template fits, reuse it rather than choosing a semantically wrong template.

## Reference-film information design standard

Each B-roll has **one semantic purpose**. Preserve the established course-film standard even when visual forms differ:

- Keep one short topic heading, normally no more than **18 Chinese characters**. Never paste a narration paragraph or a list of chapter names into the heading.
- Show **2–5** primary items on one screen. If the narration has fewer items than a template exposes, hide unused cards; never leave a **template placeholder** or invent an unrelated step merely to fill the layout.
- A primary item gets one short label. Supporting copy is optional and must explain that item; duplicated headings, raw transcript fragments, and decorative labels that compete with the narration are forbidden.
- For ordered lists, directories, comparisons, checklists, and workflows, the narration map owns focus: the **current item is yellow**, **completed items are green**, and unvisited items are gray. Focus/pointer movement occurs at the aligned spoken cue, not at evenly spaced animation times.
- A course directory must keep the whole chapter route visible while focus advances to the chapter being spoken. Do not substitute a generic three-step workflow for a chapter directory.
- Character art is a small guide or pointer, not a second information panel. It may not cover labels or enter the subtitle safety zone.

Before preview approval, reject any B-roll that still contains library example copy, repeats its heading in a card, clips a primary label, or presents more than one competing reading order.

## State-progress templates

Current item is yellow (`#e9a51a`), completed items green (`#55d4b4`), unvisited items gray (`#71818e`). State may only advance. State templates must record `stateTimeline` with `time`, `active`, `completed`, `unvisited`, and `progress`. After completion every item remains green, progress is `1`, and the yellow focus/pointer is hidden. No end-of-scene jump back to an earlier item. `validate_broll.py` independently validates timeline monotonicity, observed colors, and the final state.

The state timeline must be generated from [broll-narration-sync.md](broll-narration-sync.md). Even spacing by item count is forbidden. Every `narration-driven` registry entry declares `stateProgress`, `requiresNarrationMap`, `requiresResolvedTimeline`, and `stateDriver: broll-progress-controller`. Run `wire_broll_progress.py` during assembly; the resulting composition must contain `data-broll-progress-wired` and call `BrollProgressController.bindGsap`. Merely listing the controller path is not sufficient. Template GSAP may animate entrances but its fixed timings do not own progress state. The seekable GSAP timeline must span the **full scene duration**; otherwise a short entrance animation freezes narration-driven focus before later cues are spoken.

## Lightweight structural validation

For state progress, `validate_broll.py` checks only that the narration map and resolved timeline exist, contain the same ordered item IDs, use increasing valid intervals, and declare the shared controller. This validation is local and deterministic. Browser inspection remains optional for diagnosing layout defects; it is not required at every trigger and must not introduce AI visual-review calls.

## Real UI vs schematic UI

Set `sourceMode` to exactly one of `template`, `schematic`, or `real-ui`. A schematic must never claim to be a real operation page. A `real-ui` candidate must include:

- `realUi.originalAssetPath` and `realUi.originalAssetHash`;
- `realUi.expectedDomain` / `realUi.detectedDomain`;
- `realUi.expectedPage` / `realUi.detectedPage`;
- `humanChecks.realUiAuthenticity: "pass"`.

The validator rejects missing or mismatched provenance. The review page exposes the animation, source hash, cue, key-frame report, and state timeline together so the user can verify that a true screenshot was not replaced by a simulated page.

## New templates

If no template fits, create it only in `assets/broll/candidates/` and add a candidate entry to `planning/broll-manifest.json`. Each candidate needs a unique Candidate ID, `templateId`, `version`, source hash, `registryEntry`, cue, mapping/timeline paths, and human semantic approval. Run `validate_broll.py`, generate `build_broll_review.py`, then stop for approval. Only after explicit approval may `promote_broll.py` copy it into `approvedRoot` and insert its `registryEntry` in the registry. Do not silently leave approved reusable templates stranded in one project, and never let an unapproved candidate enter preview/render.
