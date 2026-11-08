process.env.IP_COURSE_HOME = process.env.IP_COURSE_TEST_HOME || "/nonexistent/ip-course-test-home";
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import {prepareReviewArtifacts, promoteArollFixture, setArtifactStatus, writeAudioReady, writePreviewReady, writeReadyTimeline} from "./helpers/workflow-fixture.mjs";

const root = path.resolve(import.meta.dirname, "..");

function run(script, args, cwd = root) {
  return spawnSync("python3", [path.join(root, "scripts", script), ...args], {
    cwd,
    encoding: "utf8",
  });
}

test("B-roll selection is reproducible, fixed roles bypass the library, and workflow variants diversify", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-select-"));
  const plan = {
    projectId: "demo-course",
    scenes: [
      { id: "c1", chapterId: "01", kind: "chapter" },
      { id: "s1", chapterId: "01", kind: "subchapter" },
      { id: "p1", chapterId: "01", kind: "prompt-input" },
      { id: "w1", chapterId: "01", kind: "template", family: "workflow", itemCount: 3, tags: ["linear"], progressMode: "narration-driven" },
      { id: "w2", chapterId: "01", kind: "template", family: "workflow", itemCount: 3, tags: ["linear"], progressMode: "narration-driven" },
      { id: "w3", chapterId: "02", kind: "template", family: "workflow", itemCount: 3, tags: ["iterative"], progressMode: "narration-driven" },
    ],
  };
  const planPath = path.join(dir, "plan.json");
  const out1 = path.join(dir, "lock-1.json");
  const out2 = path.join(dir, "lock-2.json");
  fs.writeFileSync(planPath, JSON.stringify(plan));

  const args = ["--project", planPath, "--registry", path.join(root, "assets/broll/template-registry.json")];
  const first = run("select_broll.py", [...args, "--output", out1]);
  const second = run("select_broll.py", [...args, "--output", out2]);
  assert.equal(first.status, 0, first.stderr);
  assert.equal(second.status, 0, second.stderr);
  assert.equal(fs.readFileSync(out1, "utf8"), fs.readFileSync(out2, "utf8"));

  const lock = JSON.parse(fs.readFileSync(out1, "utf8"));
  const byScene = Object.fromEntries(lock.selections.map((x) => [x.sceneId, x]));
  assert.equal(byScene.c1.templateId, "fixed-chapter-v1");
  assert.equal(byScene.s1.templateId, "fixed-subchapter-v1");
  assert.equal(byScene.p1.templateId, "fixed-prompt-input-v1");
  assert.notEqual(byScene.w1.templateId, byScene.w2.templateId);
});

test("approval DAG blocks missing prerequisites and invalidates only downstream dependencies", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-gate-"));
  const project = path.join(dir, "project");
  assert.equal(run("init_project.py", ["--root", project, "--project-id", "dag", "--chapters", "01"]).status, 0);
  prepareReviewArtifacts(project);
  const state = path.join(project, "approvals.json");

  const skip = run("approval_gate.py", ["request", "--file", state, "--chapter", "01", "--gate", "visual-outline", "--build-id", "outline-build"]);
  assert.notEqual(skip.status, 0);
  assert.match(skip.stderr, /ENVIRONMENT_CAST_APPROVED/);

  for (const [gate, build] of [["environment-cast", "env"], ["visual-outline", "outline"], ["aroll-images", "aroll"]]) {
    const requested = run("approval_gate.py", ["request", "--file", state, "--chapter", "01", "--gate", gate, "--build-id", `${build}-build`, "--project-root", project]);
    assert.equal(requested.status, 0, requested.stderr);
    const approved = run("approval_gate.py", ["approve", "--file", state, "--chapter", "01", "--gate", gate, "--approved-by", "human", "--build-id", `${build}-build`, "--project-root", project]);
    assert.equal(approved.status, 0, approved.stderr);
    if (gate === "environment-cast") setArtifactStatus(project, "environment-cast-plan.json", "APPROVED");
    if (gate === "visual-outline") setArtifactStatus(project, "visual-outline.json", "APPROVED");
  }
  promoteArollFixture(project);
  writeAudioReady(project);
  assert.equal(run("approval_gate.py", ["mark-ready", "--file", state, "--chapter", "01", "--milestone", "audio", "--build-id", "audio-build", "--project-root", project]).status, 0);
  assert.equal(run("approval_gate.py", ["mark-ready", "--file", state, "--chapter", "01", "--milestone", "broll-sync", "--build-id", "sync-build", "--project-root", project]).status, 0);
  writeReadyTimeline(project);
  assert.equal(run("build_full_timeline.py", ["--project-root", project]).status, 0);
  writePreviewReady(project, "preview-build");
  assert.equal(run("approval_gate.py", ["mark-ready", "--file", state, "--chapter", "01", "--milestone", "preview-ready", "--build-id", "preview-build", "--project-root", project]).status, 0);
  const previewRequest = run("approval_gate.py", ["request", "--file", state, "--chapter", "01", "--gate", "preview", "--build-id", "preview-build"]);
  assert.equal(previewRequest.status, 0, previewRequest.stderr);
  assert.equal(run("approval_gate.py", ["approve", "--file", state, "--chapter", "01", "--gate", "preview", "--approved-by", "human", "--build-id", "preview-build"]).status, 0);

  const changed = run("approval_gate.py", ["invalidate", "--file", state, "--chapter", "01", "--from", "AROLL_IMAGES_APPROVED", "--reason", "regenerated image"]);
  assert.equal(changed.status, 0, changed.stderr);
  const data = JSON.parse(fs.readFileSync(state, "utf8"));
  assert.equal(data.chapters["01"].requests["aroll-images"].buildId, "aroll-build");
  assert.equal(data.chapters["01"].approvals["aroll-images"], null);
  assert.equal(data.chapters["01"].milestones["broll-sync"], null);
  assert.equal(data.chapters["01"].approvals.preview, null);
});

test("project validator rejects punctuation at subtitle boundaries and an unlocked preview build", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-validate-"));
  const manifest = {
    projectId: "demo",
    chapters: [{ id: "01", state: "PREVIEW_APPROVED", approvedBuildId: "build-a", previewBuildId: "build-b" }],
    captions: [{ start: 0, end: 1, text: "，错误字幕。", renderedWidthPx: 500 }],
  };
  const file = path.join(dir, "manifest.json");
  fs.writeFileSync(file, JSON.stringify(manifest));
  const result = run("validate_project.py", ["--manifest", file]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /标点/);
  assert.match(result.stderr, /build ID/);
});

test("project initializer and review builder create a resumable chapter workspace", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-init-"));
  const project = path.join(dir, "course");
  const initialized = run("init_project.py", ["--root", project, "--project-id", "demo", "--chapters", "01,02"]);
  assert.equal(initialized.status, 0, initialized.stderr);
  assert.ok(fs.existsSync(path.join(project, "project.json")));
  assert.ok(fs.existsSync(path.join(project, "approvals.json")));
  assert.ok(fs.existsSync(path.join(project, "planning/aroll-manifest.json")));
  assert.ok(fs.existsSync(path.join(project, "planning/broll-manifest.json")));
  assert.ok(fs.existsSync(path.join(project, "assets/arroll/candidates")));
  assert.ok(fs.existsSync(path.join(project, "assets/arroll/approved")));
  assert.ok(fs.existsSync(path.join(project, "assets/broll/candidates")));
  assert.ok(fs.existsSync(path.join(project, "assets/broll/approved")));
  const manifest = JSON.parse(fs.readFileSync(path.join(project, "project.json"), "utf8"));
  assert.equal(manifest.fixedArollRegistry, path.join(root, "assets/arroll/template-registry.json"));
  assert.equal(manifest.arollManifest, "planning/aroll-manifest.json");
  assert.equal(manifest.brollManifest, "planning/broll-manifest.json");

  const review = run("build_review.py", ["--project", path.join(project, "project.json"), "--output", path.join(project, "reviews", "index.html")]);
  assert.equal(review.status, 0, review.stderr);
  const html = fs.readFileSync(path.join(project, "reviews", "index.html"), "utf8");
  assert.match(html, /IP 人物身份检查/);
  assert.match(html, /固定开头 A-roll/);
  assert.match(html, /opening-title/);
  assert.match(html, /opening-transition/);
  assert.match(html, /01/);
  assert.match(html, /02/);
});

test("project validator blocks preview when the referenced A-roll manifest is not approved", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-project-aroll-"));
  const project = path.join(dir, "course");
  assert.equal(run("init_project.py", ["--root", project, "--project-id", "demo", "--chapters", "01"]).status, 0);
  const projectPath = path.join(project, "project.json");
  const data = JSON.parse(fs.readFileSync(projectPath, "utf8"));
  data.chapters[0].state = "PREVIEW_APPROVED";
  data.chapters[0].previewBuildId = "build-a";
  data.chapters[0].approvedBuildId = "build-a";
  fs.writeFileSync(projectPath, JSON.stringify(data));
  const result = run("validate_project.py", ["--manifest", projectPath]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /A-roll|动作序列|candidateRoot/);
});

test("project validator blocks preview when the referenced B-roll manifest is not approved", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-project-broll-"));
  const project = path.join(dir, "course");
  assert.equal(run("init_project.py", ["--root", project, "--project-id", "demo", "--chapters", "01"]).status, 0);
  const projectPath = path.join(project, "project.json");
  const data = JSON.parse(fs.readFileSync(projectPath, "utf8"));
  data.arollManifest = null;
  data.chapters[0].state = "PREVIEW_APPROVED";
  data.chapters[0].previewBuildId = "build-a";
  data.chapters[0].approvedBuildId = "build-a";
  fs.writeFileSync(projectPath, JSON.stringify(data));
  const result = run("validate_project.py", ["--manifest", projectPath]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /B-roll|候选|approved/i);
});
