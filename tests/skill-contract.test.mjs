process.env.IP_COURSE_HOME = process.env.IP_COURSE_TEST_HOME || "/nonexistent/ip-course-test-home";
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const read = (p) => fs.readFileSync(path.join(root, p), "utf8");
const json = (p) => JSON.parse(read(p));

test("skill entrypoint is discoverable and routes every approval gate", () => {
  const text = read("SKILL.md");
  assert.match(text, /^---\nname: creating-ip-course-videos\n/m);
  assert.match(text, /description: Use when /);
  for (const state of ["ENVIRONMENT_CAST_APPROVED", "VISUAL_OUTLINE_APPROVED", "AROLL_IMAGES_APPROVED", "BROLL_SYNC_READY", "PREVIEW_APPROVED"]) {
    assert.match(text, new RegExp(state));
  }
  assert.match(text, /STOP/i);
  assert.match(text, /Image 2\.0/);
});

test("all routed references exist", () => {
  for (const file of [
    "workflow.md",
    "visual-system.md",
    "aroll-continuity.md",
    "aroll-review-system.md",
    "fixed-aroll-system.md",
    "ip-character-lock.md",
    "broll-template-system.md",
    "tts-caption-audio.md",
    "approval-gates.md",
    "parallel-production.md",
    "final-qc.md",
    "character-reference-system.md",
    "planning-review-system.md",
    "broll-narration-sync.md",
    "subtitle-segmentation.md",
    "delivery-profiles.md",
  ]) {
    assert.ok(fs.existsSync(path.join(root, "references", file)), file);
  }
});

test("skill routes generated A-roll through quarantine, real review and approved promotion", () => {
  const entry = read("SKILL.md");
  assert.match(entry, /候选隔离区|quarantine/i);
  assert.match(entry, /build_aroll_review\.py/);
  assert.match(entry, /validate_aroll\.py/);
  assert.match(entry, /promote_aroll\.py/);
  assert.match(entry, /assets\/arroll\/approved/);
  assert.doesNotMatch(entry, /ARROLL_/);
  const review = read("references/aroll-review-system.md");
  for (const label of ["完整画面", "面部", "画面左眼", "画面右眼", "Candidate ID", "素材哈希"])
    assert.match(review, new RegExp(label));
});

test("A-roll continuity defines structured action beats and enforceable cadence", () => {
  const text = read("references/aroll-continuity.md");
  assert.match(text, /3–5 秒/);
  assert.match(text, /超过 6 秒/);
  assert.match(text, /超过 8 秒/);
  assert.match(text, /cameraMovementCountsAsActionChange/);
  for (const field of ["worldLockId", "inheritsFrom", "actorAction", "gazeTarget", "propState", "durationSeconds"])
    assert.match(text, new RegExp(field));
});

test("A-roll enforcement scripts and cadence preset are shipped", () => {
  for (const file of [
    "scripts/validate_aroll.py",
    "scripts/build_aroll_review.py",
    "scripts/promote_aroll.py",
    "assets/presets/aroll-profile.json",
  ]) assert.ok(fs.existsSync(path.join(root, file)), file);
});

test("skill routes fixed opening A-roll before Image 2.0 generation", () => {
  const text = read("SKILL.md");
  assert.match(text, /fixed-aroll-system\.md/);
  assert.match(text, /opening-title/);
  assert.match(text, /opening-transition/);
  assert.match(text, /固定 A-roll.*Image 2\.0/s);
  const reference = read("references/fixed-aroll-system.md");
  assert.match(reference, /只允许.*backgroundTitle/s);
  assert.match(reference, /零可变字段/);
  assert.match(reference, /不使用.*播放器截图/s);
});

test("visual, subtitle, and audio presets preserve approved values", () => {
  const brand = json("assets/presets/brand-tokens.json");
  const subtitles = json("assets/presets/subtitle-profile.json");
  const audio = json("assets/presets/audio-profile.json");
  assert.deepEqual(brand.canvas, { width: 1920, height: 1080, fps: 30 });
  assert.equal(brand.colors.brollBackground, "#252b31");
  assert.equal(brand.grid.sizePx, 44);
  assert.equal(brand.grid.line, "rgba(132, 153, 171, 0.10)");
  assert.equal(subtitles.fontSizePx, 42);
  assert.equal(subtitles.bottomPx, 22);
  assert.equal(subtitles.maxWidthPx, 1640);
  assert.equal(audio.tts.voiceType, null, "voice is a user setting and must not ship with the skill");
  assert.equal(audio.tts.ratePercent, 0);
  assert.equal(audio.referenceVideo, undefined);
  assert.equal(audio.loudness.truePeakCeilingDbtp, -0.3);
});

test("B-roll background enforcement is routed from the skill and visual system", () => {
  const entry = read("SKILL.md");
  const visual = read("references/visual-system.md");
  for (const text of [entry, visual]) assert.match(text, /audit_broll_backgrounds\.py/);
  assert.match(visual, /locked-grid-v1/);
  assert.match(visual, /24 个注册模板/);
  assert.match(visual, /8 个共享组件/);
});

test("B-roll workflow ships executable selection, inspection, review and promotion gates", () => {
  const entry = read("SKILL.md");
  for (const name of ["validate_broll.py", "build_broll_review.py", "promote_broll.py", "broll-runtime-inspector.js"])
    assert.match(entry, new RegExp(name.replace(".", "\\.")));
  for (const file of [
    "scripts/validate_broll.py",
    "scripts/build_broll_review.py",
    "scripts/promote_broll.py",
    "assets/broll/broll-runtime-inspector.js",
    "assets/presets/broll-profile.json",
  ]) assert.ok(fs.existsSync(path.join(root, file)), file);
  const reference = read("references/broll-template-system.md");
  for (const term of ["durationSeconds", "requiredInteractions", "state timeline", "sourceMode", "realUi", "broll-progress-controller", "40%"])
    assert.match(reference, new RegExp(term));
});

test("B-roll standard forbids narration dumps and requires sparse narration-driven focus", () => {
  const reference = read("references/broll-template-system.md");
  for (const term of [
    "one semantic purpose",
    "2–5",
    "18 Chinese characters",
    "template placeholder",
    "current item is yellow",
    "completed items are green",
    "full scene duration",
  ]) assert.match(reference, new RegExp(term));
  const contentMap = read("assets/broll/library/templates/t10-content-map.html");
  assert.equal((contentMap.match(/<div[^>]+data-state-item/g) || []).length, 5);
  for (const index of [1, 2, 3, 4, 5]) assert.match(contentMap, new RegExp(`id="directory-node-${index}"`));
});

test("registry has exactly three immutable fixed template roles", () => {
  const registry = json("assets/broll/template-registry.json");
  const fixed = registry.templates.filter((x) => x.mode === "fixed");
  assert.deepEqual(
    fixed.map((x) => x.role).sort(),
    ["chapter", "prompt-input", "subchapter"],
  );
  assert.equal(new Set(fixed.map((x) => x.role)).size, 3);
  assert.ok(fixed.every((x) => x.immutable === true));
  assert.ok(registry.templates.filter((x) => x.mode === "library").length >= 21);
});

test("A-roll registry has exactly two immutable fixed roles with narrow edit surfaces", () => {
  const registry = json("assets/arroll/template-registry.json");
  assert.deepEqual(
    registry.templates.map((x) => x.role).sort(),
    ["opening-title", "opening-transition"],
  );
  assert.ok(registry.templates.every((x) => x.mode === "fixed"));
  assert.ok(registry.templates.every((x) => x.immutable === true));
  const byRole = Object.fromEntries(registry.templates.map((x) => [x.role, x]));
  assert.deepEqual(byRole["opening-title"].mutableFields, ["backgroundTitle"]);
  assert.deepEqual(byRole["opening-transition"].mutableFields, []);
});

test("fixed A-roll templates preserve the deterministic source compositions", () => {
  for (const [file, id] of [
    ["opening-title.html", "fixed-aroll-opening-title"],
    ["opening-transition.html", "fixed-aroll-opening-transition"],
  ]) {
    const html = read(`assets/arroll/fixed/${file}`);
    assert.match(html, /<template>/);
    assert.match(html, new RegExp(`data-composition-id=["']${id}["']`));
    assert.match(html, /data-width=["']1920["']/);
    assert.match(html, /data-height=["']1080["']/);
    assert.match(html, new RegExp(`window\\.__timelines\\[["']${id}["']\\]`));
    assert.match(html, new RegExp(`id=["']${id}-root["']`));
    assert.match(html, new RegExp(`#${id}-root\\{`));
    assert.doesNotMatch(html, /Math\.random|Date\.now|repeat\s*:\s*-1/);
  }
  const opening = read("assets/arroll/fixed/opening-title.html");
  assert.match(opening, /data-field=["']backgroundTitle["']/);
  assert.match(opening, /data-var-text=["']backgroundTitle["']/);
  assert.match(opening, /data-composition-variables=/);
  const transition = read("assets/arroll/fixed/opening-transition.html");
  assert.doesNotMatch(transition, /data-field=/);
  for (const html of [opening, transition]) {
    assert.doesNotMatch(html, /src=["']\.\./);
    assert.match(html, /@font-face/);
    assert.match(html, /src:local\(["']PingFang SC["']\)/);
  }
});

test("fixed templates obey deterministic HyperFrames subcomposition contract", () => {
  for (const [file, id] of [
    ["chapter.html", "fixed-chapter"],
    ["subchapter.html", "fixed-subchapter"],
    ["prompt-input.html", "fixed-prompt-input"],
  ]) {
    const html = read(`assets/broll/fixed/${file}`);
    assert.match(html, /<template>/);
    assert.match(html, new RegExp(`data-composition-id=["']${id}["']`));
    assert.match(html, /data-width=["']1920["']/);
    assert.match(html, /data-height=["']1080["']/);
    assert.match(html, new RegExp(`window\\.__timelines\\[["']${id}["']\\]`));
    assert.doesNotMatch(html, /Math\.random|Date\.now|repeat\s*:\s*-1/);
  }
});

test("IP identity contract uses unambiguous screen coordinates", () => {
  const text = read("references/ip-character-lock.md");
  assert.match(text, /screen coordinates/);
  assert.match(text, /画面左侧/);
  assert.match(text, /identityInvariants/);
  assert.match(text, /重新生成整张图/);
  assert.doesNotMatch(text, /局部涂抹.*推荐/);
});

test("skill entrypoint stays compact and routes the gated low-token workflow", () => {
  const entry = read("SKILL.md");
  assert.ok(entry.trim().split(/\s+/).length <= 520, "SKILL.md should stay cheap to load");
  for (const term of ["work order", "parallel-production.md", "isolated", "cache", "incremental_validate.py"])
    assert.match(entry, new RegExp(term, "i"));
  const parallel = read("references/parallel-production.md");
  for (const term of ["ENVIRONMENT_CAST_APPROVED", "AUDIO_READY", "contextPolicy", "Shared|shared", "serial|串行"])
    assert.match(parallel, new RegExp(term));
});

test("caption workflow ships and routes executable segmentation and timeline validation", () => {
  const entry = read("SKILL.md");
  for (const name of ["segment_captions.py", "validate_captions.py", "validate_full_timeline.py"])
    assert.match(entry, new RegExp(name.replace(".", "\\.")));
  for (const file of [
    "scripts/segment_captions.py",
    "scripts/validate_captions.py",
    "scripts/validate_full_timeline.py",
  ]) {
    const fullPath = path.join(root, file);
    assert.ok(fs.existsSync(fullPath), file);
    assert.ok((fs.statSync(fullPath).mode & 0o111) !== 0, `${file} should be executable`);
  }
  const reference = read("references/subtitle-segmentation.md");
  for (const term of ["narrationHash", "alignmentHash", "sourceAudioHash", "父时间线"])
    assert.match(reference, new RegExp(term));
});
