process.env.IP_COURSE_HOME = process.env.IP_COURSE_TEST_HOME || "/nonexistent/ip-course-test-home";
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {spawnSync} from "node:child_process";
import {prepareReviewArtifacts, promoteArollFixture, setArtifactStatus, writeAudioReady, writePreviewReady, writeReadyTimeline} from "./helpers/workflow-fixture.mjs";

const root = path.resolve(import.meta.dirname, "..");

function run(script, args) {
  return spawnSync("python3", [path.join(root, "scripts", script), ...args], {encoding: "utf8"});
}

test("chapter work orders isolate narration and carry compact hashes instead of the whole project", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-orders-"));
  const planPath = path.join(dir, "video-plan.json");
  fs.writeFileSync(planPath, JSON.stringify({
    projectId: "course",
    title: "Demo",
    outputRoot: path.join(dir, "course"),
    presets: {brand: path.join(root, "assets/presets/brand-tokens.json")},
    chapters: [
      {id: "01", narration: "第一章独有口播", scenes: [{id: "s1"}]},
      {id: "02", narration: "第二章独有口播", scenes: [{id: "s2"}]},
    ],
  }));
  const output = path.join(dir, "orders");
  const result = run("split_work_orders.py", ["--project", planPath, "--output-dir", output]);
  assert.equal(result.status, 0, result.stderr);
  const one = JSON.parse(fs.readFileSync(path.join(output, "chapter-01.json"), "utf8"));
  const raw = fs.readFileSync(path.join(output, "chapter-01.json"), "utf8");
  assert.equal(one.narration, "第一章独有口播");
  assert.doesNotMatch(raw, /第二章独有口播/);
  assert.match(one.inputHash, /^[a-f0-9]{64}$/);
  assert.equal(one.allowedWriteRoot, path.join(dir, "course", "chapters", "01"));
  const global = JSON.parse(fs.readFileSync(path.join(output, "global-brief.json"), "utf8"));
  assert.equal(global.chapterCount, 2);
  assert.equal("chapters" in global, false);
});

test("human gates open only in the approved sequential order", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-dag-"));
  const project = path.join(dir, "project");
  assert.equal(run("init_project.py", ["--root", project, "--project-id", "dag", "--chapters", "01"]).status, 0);
  prepareReviewArtifacts(project);
  const file = path.join(project, "approvals.json");
  const sequence = [["environment-cast", "env"], ["visual-outline", "outline"], ["aroll-images", "aroll"]];
  for (const [gate, build] of sequence) {
    const requested = run("approval_gate.py", ["request", "--file", file, "--chapter", "01", "--gate", gate, "--build-id", `${build}-a`, "--project-root", project]);
    assert.equal(requested.status, 0, requested.stderr);
    const approved = run("approval_gate.py", ["approve", "--file", file, "--chapter", "01", "--gate", gate, "--approved-by", "user", "--build-id", `${build}-a`, "--project-root", project]);
    assert.equal(approved.status, 0, approved.stderr);
    if (gate === "environment-cast") setArtifactStatus(project, "environment-cast-plan.json", "APPROVED");
    if (gate === "visual-outline") setArtifactStatus(project, "visual-outline.json", "APPROVED");
  }
  promoteArollFixture(project);
  const earlyPreview = run("approval_gate.py", ["request", "--file", file, "--chapter", "01", "--gate", "preview", "--build-id", "preview-a"]);
  assert.notEqual(earlyPreview.status, 0);
  assert.match(earlyPreview.stderr, /PREVIEW_READY/);
  writeAudioReady(project);
  assert.equal(run("approval_gate.py", ["mark-ready", "--file", file, "--chapter", "01", "--milestone", "audio", "--build-id", "audio-a", "--project-root", project]).status, 0);
  assert.equal(run("approval_gate.py", ["mark-ready", "--file", file, "--chapter", "01", "--milestone", "broll-sync", "--build-id", "sync-a", "--project-root", project]).status, 0);
  writeReadyTimeline(project);
  assert.equal(run("build_full_timeline.py", ["--project-root", project]).status, 0);
  writePreviewReady(project, "preview-a");
  assert.equal(run("approval_gate.py", ["mark-ready", "--file", file, "--chapter", "01", "--milestone", "preview-ready", "--build-id", "preview-a", "--project-root", project]).status, 0);
  const preview = run("approval_gate.py", ["request", "--file", file, "--chapter", "01", "--gate", "preview", "--build-id", "preview-a"]);
  assert.equal(preview.status, 0, preview.stderr);
});

test("dispatch planner caps workers and emits only dependency-ready jobs", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-dispatch-"));
  const project = path.join(dir, "course");
  assert.equal(run("init_project.py", ["--root", project, "--project-id", "demo", "--chapters", "01,02,03,04"]).status, 0);
  const output = path.join(project, "planning/dispatch.json");
  const result = run("build_dispatch_plan.py", ["--project", project, "--max-workers", "3", "--output", output]);
  assert.equal(result.status, 0, result.stderr);
  const dispatch = JSON.parse(fs.readFileSync(output, "utf8"));
  assert.equal(dispatch.maxWorkers, 3);
  assert.equal(dispatch.activeBatch.length, 3);
  assert.equal(dispatch.readyQueue.length, 4);
  assert.ok(dispatch.activeBatch.every((x) => x.stage === "environment-cast"));
  assert.ok(dispatch.activeBatch.every((x) => x.contextPolicy === "isolated"));
  for (const job of dispatch.readyQueue)
    for (const reference of job.requiredReferences)
      assert.ok(fs.existsSync(path.join(root, reference)), `${job.stage}: ${reference}`);
});

test("dispatch planner never mixes a later review stage while any chapter remains in the current global stage", () => {
  const project = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-stage-barrier-")), "course");
  assert.equal(run("init_project.py", ["--root", project, "--project-id", "demo", "--chapters", "01,02"]).status, 0);
  const approvalsPath = path.join(project, "approvals.json");
  const approvals = JSON.parse(fs.readFileSync(approvalsPath, "utf8"));
  approvals.chapters["01"].approvals["environment-cast"] = {buildId: "env-01"};
  fs.writeFileSync(approvalsPath, JSON.stringify(approvals));
  const output = path.join(project, "planning/dispatch.json");
  assert.equal(run("build_dispatch_plan.py", ["--project", project, "--output", output]).status, 0);
  const queue = JSON.parse(fs.readFileSync(output, "utf8")).readyQueue;
  assert.deepEqual(queue.map((item) => [item.chapterId, item.stage]), [["02", "environment-cast"]]);
});

test("artifact cache skips unchanged work and invalidates when an input changes", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-cache-"));
  const input = path.join(dir, "input.txt");
  const artifact = path.join(dir, "output.txt");
  const cache = path.join(dir, "cache.json");
  fs.writeFileSync(input, "v1");
  fs.writeFileSync(artifact, "render-v1");
  assert.equal(run("cache_status.py", ["record", "--cache", cache, "--key", "chapter-01", "--input", input, "--artifact", artifact]).status, 0);
  const hit = run("cache_status.py", ["check", "--cache", cache, "--key", "chapter-01", "--input", input]);
  assert.equal(hit.status, 0, hit.stderr);
  assert.match(hit.stdout, /CACHE_HIT/);
  fs.writeFileSync(input, "v2");
  const miss = run("cache_status.py", ["check", "--cache", cache, "--key", "chapter-01", "--input", input]);
  assert.equal(miss.status, 3);
  assert.match(miss.stdout, /CACHE_MISS/);
});

test("combined visual review keeps exact A-roll and B-roll review surfaces", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-review-combine-"));
  const a = path.join(dir, "aroll.html");
  const b = path.join(dir, "broll.html");
  const output = path.join(dir, "visual-review.html");
  fs.writeFileSync(a, "<html><body>A REVIEW</body></html>");
  fs.writeFileSync(b, "<html><body>B REVIEW</body></html>");
  const result = run("collect_reviews.py", ["--aroll", a, "--broll", b, "--output", output]);
  assert.equal(result.status, 0, result.stderr);
  const html = fs.readFileSync(output, "utf8");
  assert.match(html, /A-roll/);
  assert.match(html, /B-roll/);
  assert.equal((html.match(/<iframe/g) || []).length, 2);
});

test("incremental plan limits local changes to one chapter and expands shared changes to all", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-incremental-"));
  const project = path.join(dir, "course");
  assert.equal(run("init_project.py", ["--root", project, "--project-id", "demo", "--chapters", "01,02,03"]).status, 0);
  const localOut = path.join(dir, "local.json");
  assert.equal(run("incremental_validate.py", ["--project", project, "--changed", path.join(project, "chapters/02/broll/scene.html"), "--output", localOut]).status, 0);
  assert.deepEqual(JSON.parse(fs.readFileSync(localOut, "utf8")).impactedChapters, ["02"]);
  const sharedOut = path.join(dir, "shared.json");
  assert.equal(run("incremental_validate.py", ["--project", project, "--changed", path.join(project, "assets/presets/brand-tokens.json"), "--output", sharedOut]).status, 0);
  assert.deepEqual(JSON.parse(fs.readFileSync(sharedOut, "utf8")).impactedChapters, ["01", "02", "03"]);
});
