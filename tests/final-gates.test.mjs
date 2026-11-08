process.env.IP_COURSE_HOME = process.env.IP_COURSE_TEST_HOME || "/nonexistent/ip-course-test-home";
import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {spawnSync} from "node:child_process";
import {prepareReviewArtifacts, promoteArollFixture, seedGate, setArtifactStatus, writeAudioReady, writePreviewReady, writeReadyTimeline} from "./helpers/workflow-fixture.mjs";

const root = path.resolve(import.meta.dirname, "..");
const run = (script, args) => spawnSync("python3", [path.join(root, "scripts", script), ...args], {encoding: "utf8"});
const sha = (file) => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
const writeJson = (file, value) => fs.writeFileSync(file, JSON.stringify(value, null, 2));

function initializedProject() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-final-gates-"));
  const project = path.join(dir, "project");
  assert.equal(run("init_project.py", ["--root", project, "--project-id", "final", "--chapters", "01"]).status, 0);
  return project;
}

test("AUDIO_READY rejects reviewed but unpromoted A-roll images", () => {
  const project = initializedProject();
  prepareReviewArtifacts(project);
  setArtifactStatus(project, "environment-cast-plan.json", "APPROVED");
  setArtifactStatus(project, "visual-outline.json", "APPROVED");
  const approvals = path.join(project, "approvals.json");
  for (const [gate, build] of [["environment-cast", "env"], ["visual-outline", "outline"], ["aroll-images", "aroll"]]) seedGate(approvals, "01", gate, build);
  writeAudioReady(project);
  const result = run("approval_gate.py", ["mark-ready", "--file", approvals, "--chapter", "01", "--milestone", "audio", "--build-id", "audio", "--project-root", project]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /A-roll|正式素材|未批准|approved/i);
});

test("PREVIEW_READY binds the build to a composition and current full timeline", () => {
  const project = initializedProject();
  const approvals = path.join(project, "approvals.json");
  const state = JSON.parse(fs.readFileSync(approvals, "utf8"));
  state.chapters["01"].milestones["broll-sync"] = {buildId: "sync", readyAt: "fixture"};
  writeJson(approvals, state);
  writeReadyTimeline(project);
  assert.equal(run("build_full_timeline.py", ["--project-root", project]).status, 0);
  const missing = run("approval_gate.py", ["mark-ready", "--file", approvals, "--chapter", "01", "--milestone", "preview-ready", "--build-id", "preview-a", "--project-root", project]);
  assert.notEqual(missing.status, 0);
  assert.match(missing.stderr, /preview-ready\.json|预览产物|composition/i);
  writePreviewReady(project, "preview-a");
  const ready = run("approval_gate.py", ["mark-ready", "--file", approvals, "--chapter", "01", "--milestone", "preview-ready", "--build-id", "preview-a", "--project-root", project]);
  assert.equal(ready.status, 0, ready.stderr);
  const requested = run("approval_gate.py", ["request", "--file", approvals, "--chapter", "01", "--gate", "preview", "--build-id", "preview-a", "--project-root", project]);
  assert.equal(requested.status, 0, requested.stderr);
  fs.writeFileSync(path.join(project, "preview/index.html"), "changed-after-request");
  const stale = run("approval_gate.py", ["approve", "--file", approvals, "--chapter", "01", "--gate", "preview", "--build-id", "preview-a", "--approved-by", "user", "--project-root", project]);
  assert.notEqual(stale.status, 0);
  assert.match(stale.stderr, /哈希|变化|预览组合/);
});

test("render, final QC, and delivery milestones require hash-bound evidence", () => {
  const project = initializedProject();
  const approvals = path.join(project, "approvals.json");
  writeReadyTimeline(project);
  assert.equal(run("build_full_timeline.py", ["--project-root", project]).status, 0);
  writePreviewReady(project, "preview-a");
  seedGate(approvals, "01", "preview", "preview-a");
  const approved = JSON.parse(fs.readFileSync(approvals, "utf8"));
  approved.chapters["01"].approvals.preview.evidence = {
    timelineHash: sha(path.join(project, "timing/full-timeline.json")),
    previewManifestHash: sha(path.join(project, "preview/preview-ready.json")),
  };
  writeJson(approvals, approved);
  const missingRender = run("approval_gate.py", ["mark-ready", "--file", approvals, "--chapter", "01", "--milestone", "rendered", "--build-id", "render-a", "--project-root", project]);
  assert.notEqual(missingRender.status, 0);
  assert.match(missingRender.stderr, /render-ready\.json|渲染证据/);

  const renderDir = path.join(project, "renders", "01");
  fs.mkdirSync(renderDir, {recursive: true});
  const video = path.join(renderDir, "chapter.mp4");
  fs.writeFileSync(video, "render-v1");
  const timeline = path.join(project, "timing/full-timeline.json");
  const renderManifest = path.join(renderDir, "render-ready.json");
  writeJson(renderManifest, {schemaVersion: 1, status: "READY", chapterId: "01", buildId: "render-a", previewBuildId: "preview-a", videoPath: "chapter.mp4", videoHash: sha(video), fullTimelinePath: "../../timing/full-timeline.json", fullTimelineHash: sha(timeline)});
  assert.equal(run("approval_gate.py", ["mark-ready", "--file", approvals, "--chapter", "01", "--milestone", "rendered", "--build-id", "render-a", "--project-root", project]).status, 0);

  const report = path.join(renderDir, "render-qc-report.json");
  writeJson(report, {status: "PASSED", videoHash: sha(video)});
  const qcManifest = path.join(renderDir, "final-qc.json");
  writeJson(qcManifest, {schemaVersion: 1, status: "PASSED", chapterId: "01", renderHash: sha(video), reportPath: "render-qc-report.json", reportHash: sha(report), checks: {mediaProbe: true, captions: true, timeline: true, approvedAssets: true, privacyScan: true}});
  assert.equal(run("approval_gate.py", ["mark-ready", "--file", approvals, "--chapter", "01", "--milestone", "final-qc", "--build-id", "qc-a", "--project-root", project]).status, 0);

  const finalDir = path.join(project, "renders", "final");
  fs.mkdirSync(finalDir, {recursive: true});
  const master = path.join(finalDir, "master.mov");
  const upload = path.join(finalDir, "upload.mp4");
  const loudness = path.join(finalDir, "loudness.json");
  fs.writeFileSync(master, "master-v1");
  fs.writeFileSync(upload, "upload-v1");
  writeJson(loudness, {status: "PASSED", integratedLufs: -14.0, loudnessRangeLu: 6.0, truePeakDbtp: -0.5});
  writeJson(path.join(finalDir, "delivery-ready.json"), {schemaVersion: 2, status: "READY", buildId: "delivery-a", chapters: [{chapterId: "01", renderManifestPath: "../01/render-ready.json", renderManifestHash: sha(renderManifest), qcManifestPath: "../01/final-qc.json", qcManifestHash: sha(qcManifest)}], masterPath: "master.mov", masterHash: sha(master), uploadPath: "upload.mp4", uploadHash: sha(upload), fullTimelinePath: "../../timing/full-timeline.json", fullTimelineHash: sha(timeline), loudnessReportPath: "loudness.json", loudnessReportHash: sha(loudness)});
  assert.equal(run("approval_gate.py", ["mark-ready", "--file", approvals, "--chapter", "01", "--milestone", "delivery", "--build-id", "delivery-a", "--project-root", project]).status, 0);
  fs.writeFileSync(upload, "changed");
  const stale = run("approval_gate.py", ["mark-ready", "--file", approvals, "--chapter", "01", "--milestone", "delivery", "--build-id", "delivery-b", "--project-root", project]);
  assert.notEqual(stale.status, 0);
  assert.match(stale.stderr, /uploadHash|上传版|哈希/);
});

test("chapter status reports the current approval chain rather than retired tokens", () => {
  const project = initializedProject();
  const result = run("chapter_status.py", ["--project", project]);
  assert.equal(result.status, 0, result.stderr);
  const status = JSON.parse(fs.readFileSync(path.join(project, "planning/chapter-status.json"), "utf8")).chapters[0];
  assert.deepEqual(status.missing.slice(0, 3), ["ENVIRONMENT_CAST_APPROVED", "VISUAL_OUTLINE_APPROVED", "AROLL_IMAGES_APPROVED"]);
  assert.ok(status.missing.includes("BROLL_SYNC_READY"));
  assert.ok(status.missing.includes("DELIVERY_READY"));
  assert.ok(!status.missing.includes("PLAN_LOCKED"));
  assert.ok(!status.missing.includes("ASSEMBLY_READY"));
});

test("render probe validation enforces the upload profile including 48kHz audio", () => {
  const probe = {streams: [
    {codec_type: "video", codec_name: "h264", width: 1920, height: 1080, avg_frame_rate: "30/1", pix_fmt: "yuv420p"},
    {codec_type: "audio", codec_name: "aac", sample_rate: "44100", channels: 2},
  ]};
  const code = `import json,sys;sys.path.insert(0,${JSON.stringify(path.join(root, "scripts"))});from validate_render import validate_probe;print(json.dumps(validate_probe(json.loads(sys.stdin.read()), json.load(open(${JSON.stringify(path.join(root, "assets/presets/delivery-profile.json"))})))))`;
  const result = spawnSync("python3", ["-c", code], {input: JSON.stringify(probe), encoding: "utf8"});
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /48kHz|48000|采样率/);
});
