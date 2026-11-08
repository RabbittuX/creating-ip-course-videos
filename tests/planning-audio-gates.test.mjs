process.env.IP_COURSE_HOME = process.env.IP_COURSE_TEST_HOME || "/nonexistent/ip-course-test-home";
import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {spawnSync} from "node:child_process";
import {prepareReviewArtifacts, promoteArollFixture, setArtifactStatus, setCanonicalNarration} from "./helpers/workflow-fixture.mjs";

const root = path.resolve(import.meta.dirname, "..");
const run = (script, args) => spawnSync("python3", [path.join(root, "scripts", script), ...args], {encoding: "utf8"});
const sha = (file) => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");

function initProject() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-gates-"));
  const project = path.join(dir, "project");
  const result = run("init_project.py", ["--root", project, "--project-id", "audit", "--chapters", "01"]);
  assert.equal(result.status, 0, result.stderr);
  return project;
}

function gate(project, args) {
  return run("approval_gate.py", [...args, "--file", path.join(project, "approvals.json"), "--chapter", "01", "--project-root", project]);
}

function writeValidEnvironmentPlan(project) {
  setCanonicalNarration(project, "01", "完整章节口播");
  const registry = JSON.parse(fs.readFileSync(path.join(root, "assets/character-reference/registry.json"), "utf8"));
  const host = registry.characters.find((x) => x.characterId === "ip-host");
  fs.writeFileSync(path.join(project, "planning/environment-cast-plan.json"), JSON.stringify({
    schemaVersion: 2,
    status: "REVIEW_READY",
    chapters: [{
      chapterId: "01",
      narrationRange: {sourceText: "完整章节口播", sourceCharStart: 0, sourceCharEnd: 6},
      background: {backgroundId: "office-v1", label: "办公室", reason: "讲解工作流程", sharedWith: []},
      hostPresence: "required",
      cast: [{characterId: "ip-host", version: host.version, referenceHash: host.sha256}],
      sceneBible: {environmentDescription: "暖色办公室", screenBackground: "浅色信息屏", cameraFraming: "中景正面", actorPositions: ["IP人物画面左侧", "屏幕画面右侧"], continuityNotes: "保持同一机位与光线"},
      actionChain: ["进入办公室", "面向屏幕讲解", "指向结果"],
    }],
  }, null, 2));
}

test("environment-cast review cannot be requested from an empty placeholder", () => {
  const project = initProject();
  const result = gate(project, ["request", "--gate", "environment-cast", "--build-id", "env-v1"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /背景|人物|environment-cast|REVIEW_READY/);
});

test("environment-cast review requires a scene bible for background, screen, camera, and actor positions", () => {
  const project = initProject();
  writeValidEnvironmentPlan(project);
  const plan = path.join(project, "planning/environment-cast-plan.json");
  const data = JSON.parse(fs.readFileSync(plan, "utf8"));
  delete data.chapters[0].sceneBible;
  fs.writeFileSync(plan, JSON.stringify(data));
  const result = gate(project, ["request", "--gate", "environment-cast", "--build-id", "env-v1"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /sceneBible|场景圣经|屏幕背景|人物位置/);
});

test("environment-cast approval records validated artifact evidence and rejects post-request edits", () => {
  const project = initProject();
  writeValidEnvironmentPlan(project);
  const request = gate(project, ["request", "--gate", "environment-cast", "--build-id", "env-v1"]);
  assert.equal(request.status, 0, request.stderr);
  const plan = path.join(project, "planning/environment-cast-plan.json");
  const changed = JSON.parse(fs.readFileSync(plan, "utf8"));
  changed.chapters[0].background.label = "实验室";
  fs.writeFileSync(plan, JSON.stringify(changed));
  const approve = gate(project, ["approve", "--gate", "environment-cast", "--build-id", "env-v1", "--approved-by", "user"]);
  assert.notEqual(approve.status, 0);
  assert.match(approve.stderr, /变化|哈希|重新审核/);
});

test("planning approval promotes the reviewed artifact status to APPROVED", () => {
  const project = initProject();
  writeValidEnvironmentPlan(project);
  assert.equal(gate(project, ["request", "--gate", "environment-cast", "--build-id", "env-v1"]).status, 0);
  const approved = gate(project, ["approve", "--gate", "environment-cast", "--build-id", "env-v1", "--approved-by", "user"]);
  assert.equal(approved.status, 0, approved.stderr);
  assert.equal(JSON.parse(fs.readFileSync(path.join(project, "planning/environment-cast-plan.json"), "utf8")).status, "APPROVED");
});

test("visual-outline review requires narration ranges, ratios, and custom preview evidence", () => {
  const project = initProject();
  const outline = path.join(project, "planning/visual-outline.json");
  fs.writeFileSync(outline, JSON.stringify({
    schemaVersion: 2, status: "REVIEW_READY",
    chapters: [{chapterId: "01", narration: "这里是一段完整口播内容。", scenes: [{
      sceneId: "01-b1", type: "B-roll", summary: "展示流程",
      sourceText: "这里是一段完整口播内容", sourceCharStart: 0, sourceCharEnd: 12,
      plannedDurationSeconds: 3, rationale: "解释流程", designOrigin: "custom", progressMode: "static",
    }]}], overallStats: {},
  }));
  const result = run("validate_visual_outline.py", ["--outline", outline]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /预览|preview|统计|占比|stats/i);
});

test("A-roll image review cannot be requested from an empty manifest", () => {
  const project = initProject();
  const approvals = JSON.parse(fs.readFileSync(path.join(project, "approvals.json"), "utf8"));
  approvals.chapters["01"].approvals["environment-cast"] = {buildId: "env"};
  approvals.chapters["01"].approvals["visual-outline"] = {buildId: "outline"};
  fs.writeFileSync(path.join(project, "approvals.json"), JSON.stringify(approvals));
  const result = gate(project, ["request", "--gate", "aroll-images", "--build-id", "aroll-v1"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /A-roll|候选|动作序列/);
});

test("AUDIO_READY requires current narration, audio, alignment, and hash evidence", () => {
  const project = initProject();
  prepareReviewArtifacts(project);
  setArtifactStatus(project, "environment-cast-plan.json", "APPROVED");
  setArtifactStatus(project, "visual-outline.json", "APPROVED");
  promoteArollFixture(project);
  for (const [name, build] of [["environment-cast", "env"], ["visual-outline", "outline"], ["aroll-images", "aroll"]]) {
    const approvals = JSON.parse(fs.readFileSync(path.join(project, "approvals.json"), "utf8"));
    approvals.chapters["01"].requests[name] = {buildId: build};
    approvals.chapters["01"].approvals[name] = {buildId: build, approvedBy: "fixture"};
    fs.writeFileSync(path.join(project, "approvals.json"), JSON.stringify(approvals));
  }
  const missing = gate(project, ["mark-ready", "--milestone", "audio", "--build-id", "audio-v1"]);
  assert.notEqual(missing.status, 0);
  assert.match(missing.stderr, /音频|对齐|audio/i);

  const audioDir = path.join(project, "chapters/01/audio");
  fs.mkdirSync(audioDir, {recursive: true});
  const narration = path.join(audioDir, "narration.txt");
  const audio = path.join(audioDir, "narration.m4a");
  const alignment = path.join(audioDir, "alignment.json");
  fs.writeFileSync(narration, "开始讲解");
  fs.writeFileSync(audio, "audio-v1");
  fs.writeFileSync(alignment, JSON.stringify({narration: "开始讲解", audioHash: sha(audio), tokens: [
    {id: "t1", text: "开始", charStart: 0, charEnd: 2, startMs: 0, endMs: 300},
    {id: "t2", text: "讲解", charStart: 2, charEnd: 4, startMs: 300, endMs: 1000},
  ]}));
  fs.writeFileSync(path.join(audioDir, "audio-ready.json"), JSON.stringify({
    narrationPath: "narration.txt", audioPath: "narration.m4a", alignmentPath: "alignment.json",
    narrationHash: sha(narration), audioHash: sha(audio), alignmentHash: sha(alignment),
  }));
  const ready = gate(project, ["mark-ready", "--milestone", "audio", "--build-id", "audio-v1"]);
  assert.equal(ready.status, 0, ready.stderr);
  const state = JSON.parse(fs.readFileSync(path.join(project, "approvals.json"), "utf8"));
  assert.equal(state.chapters["01"].milestones.audio.evidence.audioHash, sha(audio));
});

test("planning review builders separate concise environment review from narration-bound visual outline review", () => {
  const project = initProject();
  writeValidEnvironmentPlan(project);
  const envReview = path.join(project, "reviews/environment-cast.html");
  const envResult = run("build_environment_cast_review.py", ["--project-root", project, "--output", envReview]);
  assert.equal(envResult.status, 0, envResult.stderr);
  const envHtml = fs.readFileSync(envReview, "utf8");
  for (const term of ["办公室", "ip-host", "进入办公室"])
    assert.match(envHtml, new RegExp(term));
  assert.doesNotMatch(envHtml, /完整章节口播/);

  const preview = path.join(project, "planning/custom-preview.png");
  const layout = path.join(project, "planning/custom-layout.json");
  fs.writeFileSync(preview, "preview");
  fs.writeFileSync(layout, JSON.stringify({columns: 2}));
  const narration = "先介绍背景，然后展示流程结果";
  setCanonicalNarration(project, "01", narration);
  const outline = path.join(project, "planning/visual-outline.json");
  fs.writeFileSync(outline, JSON.stringify({schemaVersion: 2, status: "REVIEW_READY", chapters: [{
    chapterId: "01", narration, scenes: [
      {sceneId: "01-a1", type: "A-roll", summary: "IP人物在办公室连续讲解本章背景", sourceText: "先介绍背景，", sourceCharStart: 0, sourceCharEnd: 6, plannedDurationSeconds: 2, rationale: "建立场景", backgroundId: "office-v1", castIds: ["ip-host"], actorAction: "走向屏幕"},
      {sceneId: "01-b1", type: "B-roll", summary: "用自定义流程图清楚展示最终执行结果", sourceText: "然后展示流程结果", sourceCharStart: 6, sourceCharEnd: narration.length, plannedDurationSeconds: 3, rationale: "展示信息", designOrigin: "custom", progressMode: "static", designPreviewPath: "planning/custom-preview.png", designPreviewHash: sha(preview), layoutSpecPath: "planning/custom-layout.json", layoutSpecHash: sha(layout)},
    ],
  }], overallStats: {}}));
  const stats = run("update_visual_outline_stats.py", ["--outline", outline]);
  assert.equal(stats.status, 0, stats.stderr);
  const validate = run("validate_visual_outline.py", ["--outline", outline]);
  assert.equal(validate.status, 0, validate.stderr);
  const outlineReview = path.join(project, "reviews/visual-outline.html");
  const review = run("build_visual_outline_review.py", ["--outline", outline, "--output", outlineReview]);
  assert.equal(review.status, 0, review.stderr);
  const html = fs.readFileSync(outlineReview, "utf8");
  for (const term of ["01-a1", "01-b1", "custom", "60.0%", "先介绍背景", "然后展示流程结果"])
    assert.match(html, new RegExp(term));
});
