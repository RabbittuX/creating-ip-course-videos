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
const hash = (file) => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");

function writeAlignment(dir, narration, audioPath) {
  const alignment = path.join(dir, "alignment.json");
  const tokens = [...narration].map((text, index) => ({
    id: `t${index + 1}`, text, charStart: index, charEnd: index + 1,
    startMs: index * 100, endMs: (index + 1) * 100,
  }));
  fs.writeFileSync(alignment, JSON.stringify({narration, audioHash: hash(audioPath), tokens}));
  return alignment;
}

test("caption segmenter separates sentences and turn clauses without splitting fixed terms", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "caption-segment-"));
  const narrationText = "即使你不会写代码，也可以跟着完成。闲话不多说，我们开始。先打开 references 文件夹，但是不要改动 Skill.md。";
  const narration = path.join(dir, "narration.txt");
  const audio = path.join(dir, "chapter.m4a");
  const output = path.join(dir, "captions.json");
  fs.writeFileSync(narration, narrationText);
  fs.writeFileSync(audio, "audio-v1");
  const alignment = writeAlignment(dir, narrationText, audio);
  const result = run("segment_captions.py", ["--narration", narration, "--alignment", alignment, "--audio", audio, "--output", output, "--chapter-id", "01"]);
  assert.equal(result.status, 0, result.stderr);
  const data = JSON.parse(fs.readFileSync(output, "utf8"));
  assert.deepEqual(data.captions.map((x) => x.text), [
    "即使你不会写代码，也可以跟着完成",
    "闲话不多说，我们开始",
    "先打开 references 文件夹",
    "但是不要改动 Skill.md",
  ]);
  assert.ok(data.captions.every((x) => x.endMs > x.startMs));
  assert.equal(data.sourceAudioHash, hash(audio));
});

test("caption validator rejects semantic joins and stale replacement audio", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "caption-validate-"));
  const audio = path.join(dir, "chapter.m4a");
  fs.writeFileSync(audio, "audio-v1");
  const narrationText = "第一句结束。第二句开始。";
  const alignment = writeAlignment(dir, narrationText, audio);
  const captions = path.join(dir, "captions.json");
  fs.writeFileSync(captions, JSON.stringify({
    alignmentHash: hash(alignment), sourceAudioHash: hash(audio), narration: narrationText,
    captions: [{id: "c1", text: "第一句结束。第二句开始", sourceCharStart: 0, sourceCharEnd: narrationText.length - 1, startMs: 0, endMs: 1200}],
  }));
  fs.writeFileSync(audio, "audio-v2");
  const result = run("validate_captions.py", ["--captions", captions, "--alignment", alignment, "--audio", audio]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /两句|语义|句末/);
  assert.match(result.stderr, /音频.*变化|重新对齐/);
});

test("caption validator rejects a turn word buried inside one cue", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "caption-turn-"));
  const audio = path.join(dir, "chapter.m4a");
  fs.writeFileSync(audio, "audio-v1");
  const narrationText = "先准备资料，但是不要直接生成。";
  const alignment = writeAlignment(dir, narrationText, audio);
  const captions = path.join(dir, "captions.json");
  fs.writeFileSync(captions, JSON.stringify({
    alignmentHash: hash(alignment), sourceAudioHash: hash(audio), narration: narrationText,
    captions: [{id: "c1", text: "先准备资料，但是不要直接生成", sourceCharStart: 0, sourceCharEnd: narrationText.length - 1, startMs: 0, endMs: 1000}],
  }));
  const result = run("validate_captions.py", ["--captions", captions, "--alignment", alignment, "--audio", audio]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /转折|但是/);
});

test("full timeline validator blocks body narration and captions inside a chapter title", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "caption-parent-timeline-"));
  const timeline = path.join(dir, "full-timeline.json");
  fs.writeFileSync(timeline, JSON.stringify({durationMs: 8000, chapters: [{
    chapterId: "01", startMs: 0, endMs: 8000,
    titleWindow: {startMs: 0, endMs: 2600},
    stingWindow: {startMs: 0, endMs: 1200},
    narrationWindow: {startMs: 2000, endMs: 8000},
    captions: [{id: "c1", text: "正文开始", startMs: 2200, endMs: 3000}],
  }]}));
  const result = run("validate_full_timeline.py", ["--timeline", timeline]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /章节页.*口播|正文口播.*章节页/);
  assert.match(result.stderr, /章节页.*字幕|字幕.*章节页/);
});

test("full timeline validator accepts caption and narration after the title interval", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "caption-parent-valid-"));
  const timeline = path.join(dir, "full-timeline.json");
  fs.writeFileSync(timeline, JSON.stringify({durationMs: 8000, chapters: [{
    chapterId: "01", startMs: 0, endMs: 8000,
    titleWindow: {startMs: 0, endMs: 2600},
    stingWindow: {startMs: 200, endMs: 1200},
    narrationWindow: {startMs: 2600, endMs: 8000},
    captions: [{id: "c1", text: "正文开始", startMs: 2700, endMs: 3400}],
  }]}));
  const result = run("validate_full_timeline.py", ["--timeline", timeline]);
  assert.equal(result.status, 0, result.stderr);
});

test("project initializer creates the caption and parent timeline contract", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "caption-project-init-"));
  const project = path.join(dir, "project");
  const result = run("init_project.py", ["--root", project, "--project-id", "demo", "--chapters", "01,02"]);
  assert.equal(result.status, 0, result.stderr);
  const manifest = JSON.parse(fs.readFileSync(path.join(project, "project.json"), "utf8"));
  assert.equal(manifest.fullTimeline, "timing/full-timeline.json");
  assert.ok(fs.existsSync(path.join(project, manifest.fullTimeline)));
  for (const id of ["01", "02"])
    assert.ok(fs.existsSync(path.join(project, "chapters", id, "timing", "captions.json")));
});

test("project validation invokes the full parent timeline check before preview", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "caption-project-gate-"));
  const timeline = path.join(dir, "full-timeline.json");
  fs.writeFileSync(timeline, JSON.stringify({durationMs: 5000, chapters: [{
    chapterId: "01", startMs: 0, endMs: 5000,
    titleWindow: {startMs: 0, endMs: 2000}, stingWindow: {startMs: 0, endMs: 800},
    narrationWindow: {startMs: 1500, endMs: 5000}, captions: [],
  }]}));
  const project = path.join(dir, "project.json");
  fs.writeFileSync(project, JSON.stringify({
    projectId: "demo", fullTimeline: "full-timeline.json",
    chapters: [{id: "01", state: "PREVIEW_APPROVED", previewBuildId: "p1", approvedBuildId: "p1"}], captions: [],
  }));
  const result = run("validate_project.py", ["--manifest", project]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /父时间线|章节页.*口播|正文口播.*章节页/);
});

test("preview validation cannot bypass the parent timeline by omitting its path", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "caption-project-missing-parent-"));
  const project = path.join(dir, "project.json");
  fs.writeFileSync(project, JSON.stringify({
    projectId: "legacy-demo",
    chapters: [{id: "01", state: "PREVIEW_REVIEW"}], captions: [],
  }));
  const result = run("validate_project.py", ["--manifest", project]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /fullTimeline|完整父时间线/);
});

test("caption segmenter uses a real word-alignment pause as a semantic boundary", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "caption-pause-"));
  const narrationText = "先完成准备再开始执行";
  const narration = path.join(dir, "narration.txt");
  const audio = path.join(dir, "chapter.m4a");
  const alignment = path.join(dir, "alignment.json");
  const output = path.join(dir, "captions.json");
  fs.writeFileSync(narration, narrationText);
  fs.writeFileSync(audio, "audio-v1");
  fs.writeFileSync(alignment, JSON.stringify({narration: narrationText, audioHash: hash(audio), tokens: [
    {id: "t1", text: "先完成准备", charStart: 0, charEnd: 5, startMs: 0, endMs: 500},
    {id: "t2", text: "再开始执行", charStart: 5, charEnd: 10, startMs: 1000, endMs: 1500},
  ]}));
  const result = run("segment_captions.py", ["--narration", narration, "--alignment", alignment, "--audio", audio, "--output", output]);
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(fs.readFileSync(output, "utf8")).captions.map((x) => x.text), ["先完成准备", "再开始执行"]);
});

test("caption validation requires current narration and an audio-bound alignment", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "caption-current-source-"));
  const narration = path.join(dir, "narration.txt");
  const audio = path.join(dir, "chapter.m4a");
  fs.writeFileSync(narration, "当前口播");
  fs.writeFileSync(audio, "audio-v1");
  const alignment = writeAlignment(dir, "当前口播", audio);
  const output = path.join(dir, "captions.json");
  assert.equal(run("segment_captions.py", ["--narration", narration, "--alignment", alignment, "--audio", audio, "--output", output]).status, 0);
  fs.writeFileSync(narration, "已经替换的口播");
  const stale = run("validate_captions.py", ["--captions", output, "--alignment", alignment, "--audio", audio, "--narration", narration]);
  assert.notEqual(stale.status, 0);
  assert.match(stale.stderr, /口播.*变化|重新生成/);

  const unbound = JSON.parse(fs.readFileSync(alignment, "utf8"));
  delete unbound.audioHash;
  fs.writeFileSync(alignment, JSON.stringify(unbound));
  const missingHash = run("segment_captions.py", ["--narration", narration, "--alignment", alignment, "--audio", audio, "--output", output]);
  assert.notEqual(missingHash.status, 0);
  assert.match(missingHash.stderr, /audioHash|音频.*哈希/);
});
