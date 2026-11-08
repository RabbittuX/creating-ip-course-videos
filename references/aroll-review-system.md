# A-roll review system

Use this stage for every generated A-roll candidate. Fixed opening A-roll remains governed by `fixed-aroll-system.md` and is displayed for placement review without promotion.

## Quarantine and manifest

Image 2.0 output goes to `assets/arroll/candidates/`, never directly to a composition. Add the Candidate ID,素材哈希, action fields, duration, identity checks, continuity checks, and crop paths to `planning/aroll-manifest.json`.

Recommended human-review evidence for each candidate:

- 完整画面;
- 面部 crop;
- separate 画面左眼 and 画面右眼 crops;
- Candidate ID and素材哈希;
- narration cue, actor action, gaze target, prop state, and duration;
- the preceding action frame in sequence order when one exists.

The crop evidence may be produced mechanically from approved crop boxes. It is a viewing aid, not automated visual judgement. Missing optional crops should be visible in the review page but must not trigger model-based rejection or automatic regeneration. Never guess eye identity from screen coordinates without displaying the labeled crops to the reviewer.

## Validate and build

```bash
python3 scripts/validate_aroll.py \
  --manifest <project>/planning/aroll-manifest.json \
  --profile assets/presets/aroll-profile.json \
  --mode review

python3 scripts/build_aroll_review.py \
  --manifest <project>/planning/aroll-manifest.json \
  --profile assets/presets/aroll-profile.json \
  --output <project>/reviews/aroll/index.html
```

Serve the review directory over a verified local HTTP server. Before sending the link, confirm the URL responds, every review image loads, and the visible Candidate IDs match the pending build. Do not provide a bare `file://` path as the only review route.

The page must display blocking errors, cadence warnings, status, full frame, face, both eyes, narration, action, prop state, and exact duration. The reviewer approves exact Candidate IDs, not an implied group of unseen files.

## Promote

After explicit user approval:

```bash
python3 scripts/promote_aroll.py \
  --manifest <project>/planning/aroll-manifest.json \
  --profile assets/presets/aroll-profile.json \
  --candidate-id <candidate-id> \
  --approved-by user
```

Promotion copies the hash-matched image to `assets/arroll/approved/` and records reviewer and UTC time. Missing structural fields, stale hashes, hard cadence violations, or absent explicit human approval block promotion. Identity, anatomy, style, background continuity, and crop quality are decided by the user, not by an automatic semantic checker. Regeneration creates a new candidate and invalidates downstream preview approval.
