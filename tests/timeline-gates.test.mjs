process.env.IP_COURSE_HOME = process.env.IP_COURSE_TEST_HOME || "/nonexistent/ip-course-test-home";
import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {spawnSync} from "node:child_process";

const root = path.resolve(import.meta.dirname, "..");
const run = (script, args) => spawnSync("python3", [path.join(root, "scripts", script), ...args], {encoding: "utf8"});
const sha = (file) => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");

test("B-roll resolver requires the current audio and stores its hash", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "broll-audio-proof-"));
  const audio = path.join(dir, "narration.m4a");
  const alignment = path.join(dir, "alignment.json");
  const mapping = path.join(dir, "map.json");
  const output = path.join(dir, "timeline.json");
  fs.writeFileSync(audio, "audio-v1");
  fs.writeFileSync(alignment, JSON.stringify({audioHash: sha(audio), tokens: [{id: "t1", text: "第一项", charStart: 0, charEnd: 3, startMs: 0, endMs: 500}]}));
  fs.writeFileSync(mapping, JSON.stringify({narration: "第一项", items: [{sceneId: "flow", itemId: "one", sourceCharStart: 0, sourceCharEnd: 3, switchAtChar: 0, triggerText: "第一项"}]}));
  const result = run("resolve_broll_timeline.py", ["--map", mapping, "--alignment", alignment, "--audio", audio, "--output", output]);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(fs.readFileSync(output, "utf8")).sourceAudioHash, sha(audio));
  fs.writeFileSync(audio, "audio-v2");
  const stale = run("resolve_broll_timeline.py", ["--map", mapping, "--alignment", alignment, "--audio", audio, "--output", output]);
  assert.notEqual(stale.status, 0);
  assert.match(stale.stderr, /音频.*变化|重新对齐/);
});

test("full timeline builder offsets chapter-local title, narration, and captions", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "full-timeline-build-"));
  const project = path.join(dir, "project");
  assert.equal(run("init_project.py", ["--root", project, "--project-id", "demo", "--chapters", "01,02"]).status, 0);
  for (const [id, duration] of [["01", 5000], ["02", 4000]]) {
    const spec = path.join(project, "chapters", id, "timing", "chapter-timeline.json");
    fs.writeFileSync(spec, JSON.stringify({
      chapterId: id, durationMs: duration,
      titleWindow: {startMs: 0, endMs: 1000}, stingWindow: {startMs: 100, endMs: 700},
      narrationWindow: {startMs: 1000, endMs: duration},
      captions: [{id: `${id}-c1`, text: "正文", startMs: 1100, endMs: 1500}],
    }));
  }
  const result = run("build_full_timeline.py", ["--project-root", project]);
  assert.equal(result.status, 0, result.stderr);
  const timeline = JSON.parse(fs.readFileSync(path.join(project, "timing/full-timeline.json"), "utf8"));
  assert.equal(timeline.durationMs, 9000);
  assert.deepEqual(timeline.chapters.map((x) => [x.startMs, x.endMs]), [[0, 5000], [5000, 9000]]);
  assert.equal(timeline.chapters[1].titleWindow.startMs, 5000);
  assert.equal(timeline.chapters[1].narrationWindow.startMs, 6000);
  assert.equal(timeline.chapters[1].captions[0].startMs, 6100);
});

test("PREVIEW_READY cannot be marked without a valid full parent timeline", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "preview-ready-proof-"));
  const project = path.join(dir, "project");
  assert.equal(run("init_project.py", ["--root", project, "--project-id", "demo", "--chapters", "01"]).status, 0);
  const approvalsPath = path.join(project, "approvals.json");
  const approvals = JSON.parse(fs.readFileSync(approvalsPath, "utf8"));
  approvals.chapters["01"].milestones["broll-sync"] = {buildId: "sync", readyAt: "fixture"};
  fs.writeFileSync(approvalsPath, JSON.stringify(approvals));
  const result = run("approval_gate.py", ["mark-ready", "--file", approvalsPath, "--chapter", "01", "--milestone", "preview-ready", "--build-id", "preview", "--project-root", project]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /父时间线|字幕|preview/i);
});
