process.env.IP_COURSE_HOME = process.env.IP_COURSE_TEST_HOME || "/nonexistent/ip-course-test-home";
import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {spawnSync} from "node:child_process";
import {prepareReviewArtifacts, promoteArollFixture, setArtifactStatus, writeAudioReady, writePreviewReady, writeReadyTimeline} from "./helpers/workflow-fixture.mjs";

const root = path.resolve(import.meta.dirname, "..");
const run = (script, args) => spawnSync("python3", [path.join(root, "scripts", script), ...args], {encoding: "utf8"});
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");
const json = (file) => JSON.parse(read(file));
const sha = (file) => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");

test("skill routes the approved sequential workflow and four human stops", () => {
  const entry = read("SKILL.md");
  for (const token of ["ENVIRONMENT_CAST_APPROVED", "VISUAL_OUTLINE_APPROVED", "AROLL_IMAGES_APPROVED", "BROLL_SYNC_READY", "PREVIEW_APPROVED"])
    assert.match(entry, new RegExp(token));
  assert.doesNotMatch(entry, /generate A-roll, B-roll, and chapter audio in parallel/i);
  assert.match(entry, /按章节串行|serial/i);
});

test("bundled character registry is a hash-locked placeholder, not a real IP", () => {
  const registry = json("assets/character-reference/registry.json");
  assert.equal(registry.example, true);
  const host = registry.characters.find((x) => x.role === "required-host");
  assert.equal(host.status, "approved");
  assert.match(host.sha256, /^[a-f0-9]{64}$/);
  assert.ok(fs.existsSync(path.join(root, "assets/character-reference", host.canonicalPath)));
  const checked = run("validate_character_registry.py", ["--registry", path.join(root, "assets/character-reference/registry.json")]);
  assert.equal(checked.status, 0, checked.stderr);
});

test("approval DAG enforces environment, outline, A-roll, audio, B-roll sync, then preview", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-sequential-"));
  const project = path.join(dir, "project");
  assert.equal(run("init_project.py", ["--root", project, "--project-id", "dag", "--chapters", "01"]).status, 0);
  prepareReviewArtifacts(project);
  const file = path.join(project, "approvals.json");
  const early = run("approval_gate.py", ["request", "--file", file, "--chapter", "01", "--gate", "visual-outline", "--build-id", "outline-a"]);
  assert.notEqual(early.status, 0);
  for (const [gate, build] of [["environment-cast", "env-a"], ["visual-outline", "outline-a"], ["aroll-images", "aroll-a"]]) {
    assert.equal(run("approval_gate.py", ["request", "--file", file, "--chapter", "01", "--gate", gate, "--build-id", build, "--project-root", project]).status, 0);
    assert.equal(run("approval_gate.py", ["approve", "--file", file, "--chapter", "01", "--gate", gate, "--build-id", build, "--approved-by", "user", "--project-root", project]).status, 0);
    if (gate === "environment-cast") setArtifactStatus(project, "environment-cast-plan.json", "APPROVED");
    if (gate === "visual-outline") setArtifactStatus(project, "visual-outline.json", "APPROVED");
  }
  promoteArollFixture(project);
  writeAudioReady(project);
  assert.equal(run("approval_gate.py", ["mark-ready", "--file", file, "--chapter", "01", "--milestone", "audio", "--build-id", "audio-a", "--project-root", project]).status, 0);
  assert.equal(run("approval_gate.py", ["mark-ready", "--file", file, "--chapter", "01", "--milestone", "broll-sync", "--build-id", "sync-a", "--project-root", project]).status, 0);
  writeReadyTimeline(project);
  assert.equal(run("build_full_timeline.py", ["--project-root", project]).status, 0);
  writePreviewReady(project, "preview-a");
  assert.equal(run("approval_gate.py", ["mark-ready", "--file", file, "--chapter", "01", "--milestone", "preview-ready", "--build-id", "preview-a", "--project-root", project]).status, 0);
  assert.equal(run("approval_gate.py", ["request", "--file", file, "--chapter", "01", "--gate", "preview", "--build-id", "preview-a"]).status, 0);
});

test("B-roll narration map resolves unique triggers to aligned word times", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-broll-map-"));
  const mapping = path.join(dir, "map.json");
  const alignment = path.join(dir, "alignment.json");
  const audio = path.join(dir, "narration.m4a");
  const output = path.join(dir, "timeline.json");
  fs.writeFileSync(audio, "audio-v1");
  fs.writeFileSync(mapping, JSON.stringify({narration: "先介绍 references，再介绍 scripts，最后介绍 assets。", items: [
    {itemId: "references", label: "references/", sourceCharStart: 4, sourceCharEnd: 14, triggerText: "references"},
    {itemId: "scripts", label: "scripts/", sourceCharStart: 19, sourceCharEnd: 26, triggerText: "scripts"},
    {itemId: "assets", label: "assets/", sourceCharStart: 32, sourceCharEnd: 38, triggerText: "assets"},
  ]}));
  fs.writeFileSync(alignment, JSON.stringify({audioHash: sha(audio), tokens: [
    {text: "references", charStart: 4, charEnd: 14, startMs: 1000, endMs: 1600},
    {text: "scripts", charStart: 19, charEnd: 26, startMs: 2600, endMs: 3100},
    {text: "assets", charStart: 32, charEnd: 38, startMs: 4100, endMs: 4550},
  ]}));
  const result = run("resolve_broll_timeline.py", ["--map", mapping, "--alignment", alignment, "--audio", audio, "--output", output]);
  assert.equal(result.status, 0, result.stderr);
  const timeline = JSON.parse(fs.readFileSync(output, "utf8"));
  assert.deepEqual(timeline.items.map((x) => x.activeAtMs), [1000, 2600, 4100]);
  assert.deepEqual(timeline.items.map((x) => x.completeAtMs), [2600, 4100, 4550]);
});

test("project initializer creates planning and timing contracts", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-init-v3-"));
  const project = path.join(dir, "project");
  assert.equal(run("init_project.py", ["--root", project, "--project-id", "demo", "--chapters", "01"]).status, 0);
  for (const file of ["planning/narration-manifest.json", "planning/environment-cast-plan.json", "planning/visual-outline.json", "planning/creative-directives.json", "chapters/01/planning/broll-narration-map.json", "chapters/01/timing/broll-state-timeline.json"])
    assert.ok(fs.existsSync(path.join(project, file)), file);
  const manifest = JSON.parse(fs.readFileSync(path.join(project, "project.json"), "utf8"));
  assert.ok(path.isAbsolute(manifest.characterRegistry));
  assert.ok(fs.existsSync(manifest.characterRegistry));
});

test("duplicate B-roll trigger text is blocked unless occurrence is disambiguated", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-trigger-"));
  const file = path.join(dir, "map.json");
  fs.writeFileSync(file, JSON.stringify({narration: "先说规则，再重复规则", items: [
    {itemId: "rule", sourceCharStart: 0, sourceCharEnd: 10, triggerText: "规则"},
  ]}));
  const result = run("validate_broll_narration_map.py", ["--map", file]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /不唯一|延长信号|triggerOccurrence/);
});

test("state consistency validator rejects project and approval disagreement", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-state-"));
  const project = path.join(dir, "project");
  assert.equal(run("init_project.py", ["--root", project, "--project-id", "demo", "--chapters", "01"]).status, 0);
  const manifestPath = path.join(project, "project.json");
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  manifest.chapters[0].state = "PREVIEW_APPROVED";
  fs.writeFileSync(manifestPath, JSON.stringify(manifest));
  const result = run("validate_state_consistency.py", ["--project", manifestPath, "--approvals", path.join(project, "approvals.json")]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /状态不一致/);
});

test("delivery profile locks a high-quality upload derivative", () => {
  const profile = json("assets/presets/delivery-profile.json");
  assert.equal(profile.upload.width, 1920);
  assert.equal(profile.upload.height, 1080);
  assert.equal(profile.upload.fps, 30);
  assert.ok(profile.upload.video.crf >= 20 && profile.upload.video.crf <= 22);
  assert.ok(profile.upload.audio.bitrateKbps >= 160);
  assert.equal(profile.upload.faststart, true);
});
