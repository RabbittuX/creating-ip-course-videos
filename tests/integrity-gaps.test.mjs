process.env.IP_COURSE_HOME = process.env.IP_COURSE_TEST_HOME || "/nonexistent/ip-course-test-home";
import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {spawnSync} from "node:child_process";
import {
  prepareReviewArtifacts,
  promoteArollFixture,
  seedGate,
  setCanonicalNarration,
  setArtifactStatus,
  writeAudioReady,
  writePreviewReady,
  writeReadyTimeline,
} from "./helpers/workflow-fixture.mjs";

const root = path.resolve(import.meta.dirname, "..");
const run = (script, args) => spawnSync("python3", [path.join(root, "scripts", script), ...args], {encoding: "utf8"});
const sha = (file) => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
const writeJson = (file, value) => fs.writeFileSync(file, JSON.stringify(value, null, 2));

function init(chapters = "01") {
  const project = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "ip-integrity-")), "project");
  const result = run("init_project.py", ["--root", project, "--project-id", "integrity", "--chapters", chapters]);
  assert.equal(result.status, 0, result.stderr);
  return project;
}

function gate(project, chapter, args) {
  return run("approval_gate.py", [...args, "--file", path.join(project, "approvals.json"), "--chapter", chapter, "--project-root", project]);
}

test("narration index becomes READY only after every project chapter is canonicalized", () => {
  const project = init("01,02");
  const one = path.join(project, "one.txt");
  const two = path.join(project, "two.txt");
  fs.writeFileSync(one, "第一章口播");
  fs.writeFileSync(two, "第二章口播");
  assert.equal(run("index_narration.py", ["--project-root", project, "--chapter", "01", "--text-file", one]).status, 0);
  let manifest = JSON.parse(fs.readFileSync(path.join(project, "planning/narration-manifest.json"), "utf8"));
  assert.equal(manifest.status, "DRAFT");
  assert.equal(run("index_narration.py", ["--project-root", project, "--chapter", "02", "--text-file", two]).status, 0);
  manifest = JSON.parse(fs.readFileSync(path.join(project, "planning/narration-manifest.json"), "utf8"));
  assert.equal(manifest.status, "READY");
  assert.deepEqual(manifest.chapters.map((item) => item.narration), ["第一章口播", "第二章口播"]);
});

test("AUDIO_READY rejects narration that differs from the canonical approved script", () => {
  const project = init();
  prepareReviewArtifacts(project);
  setArtifactStatus(project, "environment-cast-plan.json", "APPROVED");
  setArtifactStatus(project, "visual-outline.json", "APPROVED");
  promoteArollFixture(project);
  const approvals = path.join(project, "approvals.json");
  for (const [name, build] of [["environment-cast", "env"], ["visual-outline", "outline"], ["aroll-images", "aroll"]])
    seedGate(approvals, "01", name, build);
  writeAudioReady(project, "01", "完全不同的口播");
  const result = gate(project, "01", ["mark-ready", "--milestone", "audio", "--build-id", "audio-v1"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /主口播|唯一口播|narration-manifest|不一致/);
});

test("visual outline rejects gaps and overlaps in narration coverage", () => {
  const project = init();
  prepareReviewArtifacts(project);
  const outlinePath = path.join(project, "planning/visual-outline.json");
  const outline = JSON.parse(fs.readFileSync(outlinePath, "utf8"));
  outline.chapters[0].narration = "甲乙丙丁";
  outline.chapters[0].scenes[0].sourceText = "甲乙";
  outline.chapters[0].scenes[0].sourceCharStart = 0;
  outline.chapters[0].scenes[0].sourceCharEnd = 2;
  writeJson(outlinePath, outline);
  const result = run("validate_visual_outline.py", ["--outline", outlinePath, "--project-root", project]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /完整覆盖|空洞|连续|主口播/);
});

test("chapter-scoped visual outline validation still checks full-film overall stats", () => {
  const project = init("01,02");
  setCanonicalNarration(project, "01", "甲乙");
  setCanonicalNarration(project, "02", "丙丁");
  const scene = (chapterId, text) => ({
    chapterId,
    narration: text,
    scenes: [{
      sceneId: `${chapterId}-a1`, type: "A-roll", summary: "人物完成本章核心讲解",
      sourceText: text, sourceCharStart: 0, sourceCharEnd: 2,
      plannedDurationSeconds: 2, rationale: "建立讲解场景", backgroundId: "office-v1",
      castIds: ["ip-host"], actorAction: "面向屏幕讲解",
    }],
    stats: {totalSeconds: 2, aroll: {seconds: 2, ratio: 1}, broll: {seconds: 0, ratio: 0}},
  });
  writeJson(path.join(project, "planning/visual-outline.json"), {
    schemaVersion: 2,
    status: "REVIEW_READY",
    chapters: [scene("01", "甲乙"), scene("02", "丙丁")],
    overallStats: {totalSeconds: 4, aroll: {seconds: 4, ratio: 1}, broll: {seconds: 0, ratio: 0}},
  });
  const result = run("validate_visual_outline.py", [
    "--outline", path.join(project, "planning/visual-outline.json"),
    "--chapter", "01",
    "--project-root", project,
  ]);
  assert.equal(result.status, 0, result.stderr);
});

test("a chapter cannot enter the next review stage before every chapter finishes the current global stage", () => {
  const project = init("01,02");
  prepareReviewArtifacts(project, "01");
  const approvals = path.join(project, "approvals.json");
  seedGate(approvals, "01", "environment-cast", "env-01");
  const result = gate(project, "01", ["request", "--gate", "visual-outline", "--build-id", "outline-01"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /全部章节|全片|02|ENVIRONMENT_CAST_APPROVED/);
});

test("A-roll review requires sequences and candidates for the requested chapter and every A-roll scene", () => {
  const project = init("01,02");
  prepareReviewArtifacts(project, "01");
  const outlinePath = path.join(project, "planning/visual-outline.json");
  const outline = JSON.parse(fs.readFileSync(outlinePath, "utf8"));
  outline.chapters.push({
    chapterId: "02", narration: "继续讲解", scenes: [{
      sceneId: "02-a1", type: "A-roll", summary: "继续讲解",
      sourceText: "继续讲解", sourceCharStart: 0, sourceCharEnd: 4,
      plannedDurationSeconds: 2, rationale: "延续场景", backgroundId: "office-v1",
      castIds: ["ip-host"], actorAction: "继续面向屏幕讲解",
    }], stats: {totalSeconds: 2, aroll: {seconds: 2, ratio: 1}, broll: {seconds: 0, ratio: 0}},
  });
  outline.overallStats = {totalSeconds: 4, aroll: {seconds: 4, ratio: 1}, broll: {seconds: 0, ratio: 0}};
  writeJson(outlinePath, outline);
  const approvals = path.join(project, "approvals.json");
  for (const chapter of ["01", "02"]) {
    seedGate(approvals, chapter, "environment-cast", `env-${chapter}`);
    seedGate(approvals, chapter, "visual-outline", `outline-${chapter}`);
  }
  const result = gate(project, "02", ["request", "--gate", "aroll-images", "--build-id", "aroll-02"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /章节 02|02-a1|覆盖/);
});

test("PREVIEW_READY rejects a parent timeline that omits a project chapter", () => {
  const project = init("01,02");
  const approvalsPath = path.join(project, "approvals.json");
  const approvals = JSON.parse(fs.readFileSync(approvalsPath, "utf8"));
  for (const chapter of ["01", "02"])
    approvals.chapters[chapter].milestones["broll-sync"] = {buildId: `sync-${chapter}`, readyAt: "fixture"};
  writeJson(approvalsPath, approvals);
  writeReadyTimeline(project, "01");
  const timeline = path.join(project, "timing/full-timeline.json");
  writeJson(timeline, {schemaVersion: 1, projectId: "integrity", status: "READY", durationMs: 2000, chapters: [{
    chapterId: "01", startMs: 0, endMs: 2000,
    titleWindow: {startMs: 0, endMs: 400}, stingWindow: {startMs: 0, endMs: 250},
    narrationWindow: {startMs: 500, endMs: 1800}, captions: [],
  }]});
  writePreviewReady(project, "preview-v1", "01");
  const result = gate(project, "01", ["mark-ready", "--milestone", "preview-ready", "--build-id", "preview-v1"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /全部章节|章节 02|完整父时间线/);
});

test("static B-roll must bind an approved manifest candidate and real composition", () => {
  const project = init();
  prepareReviewArtifacts(project);
  const preview = path.join(project, "planning/static-preview.png");
  const layout = path.join(project, "planning/static-layout.json");
  fs.writeFileSync(preview, "preview");
  writeJson(layout, {columns: 2});
  const outlinePath = path.join(project, "planning/visual-outline.json");
  const outline = JSON.parse(fs.readFileSync(outlinePath, "utf8"));
  outline.chapters[0].scenes = [{
    sceneId: "01-b1", type: "B-roll", summary: "展示静态对比",
    sourceText: "开始讲解", sourceCharStart: 0, sourceCharEnd: 4,
    plannedDurationSeconds: 2, rationale: "展示信息", designOrigin: "custom", progressMode: "static",
    designPreviewPath: "planning/static-preview.png", designPreviewHash: sha(preview),
    layoutSpecPath: "planning/static-layout.json", layoutSpecHash: sha(layout),
  }];
  outline.chapters[0].stats = {totalSeconds: 2, aroll: {seconds: 0, ratio: 0}, broll: {seconds: 2, ratio: 1}};
  outline.overallStats = outline.chapters[0].stats;
  writeJson(outlinePath, outline);
  const result = run("validate_broll_sync_ready.py", ["--project-root", project, "--chapter", "01"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /B-roll.*清单|01-b1|compositionPath|正式/);
});

test("approval transitions synchronize project.json and chapter-status.json", () => {
  const project = init();
  prepareReviewArtifacts(project);
  assert.equal(gate(project, "01", ["request", "--gate", "environment-cast", "--build-id", "env"]).status, 0);
  assert.equal(gate(project, "01", ["approve", "--gate", "environment-cast", "--build-id", "env", "--approved-by", "user"]).status, 0);
  const manifest = JSON.parse(fs.readFileSync(path.join(project, "project.json"), "utf8"));
  const status = JSON.parse(fs.readFileSync(path.join(project, "chapters/01/chapter-status.json"), "utf8"));
  assert.equal(manifest.chapters[0].state, "ENVIRONMENT_CAST_APPROVED");
  assert.equal(status.state, "ENVIRONMENT_CAST_APPROVED");
  const checked = run("validate_state_consistency.py", ["--project", path.join(project, "project.json"), "--approvals", path.join(project, "approvals.json")]);
  assert.equal(checked.status, 0, checked.stderr);
});

test("PREVIEW_READY is invalidated when creative directives change", () => {
  const project = init();
  const approvalsPath = path.join(project, "approvals.json");
  const approvals = JSON.parse(fs.readFileSync(approvalsPath, "utf8"));
  approvals.chapters["01"].milestones["broll-sync"] = {buildId: "sync", readyAt: "fixture"};
  writeJson(approvalsPath, approvals);
  writeReadyTimeline(project, "01");
  assert.equal(run("build_full_timeline.py", ["--project-root", project]).status, 0);
  writePreviewReady(project, "preview-v1", "01");
  const directives = path.join(project, "planning/creative-directives.json");
  writeJson(directives, {schemaVersion: 1, directives: [{id: "speed", instruction: "1:04 前 1.25 倍速"}]});
  const result = gate(project, "01", ["mark-ready", "--milestone", "preview-ready", "--build-id", "preview-v1"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /creative|创意指令|特效|倍速|哈希/i);
});

test("actual duration report requires re-review when scene or A/B ratio drift exceeds thresholds", () => {
  const project = init();
  prepareReviewArtifacts(project);
  writeAudioReady(project, "01", "开始讲解");
  const alignmentPath = path.join(project, "chapters/01/audio/alignment.json");
  const alignment = JSON.parse(fs.readFileSync(alignmentPath, "utf8"));
  alignment.tokens[0].endMs = 4500;
  writeJson(alignmentPath, alignment);
  const audioReadyPath = path.join(project, "chapters/01/audio/audio-ready.json");
  const audioReady = JSON.parse(fs.readFileSync(audioReadyPath, "utf8"));
  audioReady.alignmentHash = sha(alignmentPath);
  writeJson(audioReadyPath, audioReady);
  const report = path.join(project, "planning/actual-duration-report.json");
  const result = run("build_actual_duration_report.py", ["--project-root", project, "--output", report]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /重新审核|偏差|1.*秒|5%/);
  assert.equal(JSON.parse(fs.readFileSync(report, "utf8")).status, "REVIEW_REQUIRED");
});

test("DELIVERY_READY requires one aggregate full-video manifest covering every chapter", () => {
  const project = init("01,02");
  const approvalsPath = path.join(project, "approvals.json");
  const approvals = JSON.parse(fs.readFileSync(approvalsPath, "utf8"));
  for (const cid of ["01", "02"])
    approvals.chapters[cid].milestones["final-qc"] = {buildId: `qc-${cid}`, readyAt: "fixture"};
  writeJson(approvalsPath, approvals);
  const result = gate(project, "01", ["mark-ready", "--milestone", "delivery", "--build-id", "delivery-v1"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /全片|aggregate|renders\/final|delivery-ready/i);
});
