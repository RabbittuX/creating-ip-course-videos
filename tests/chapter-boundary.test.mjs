process.env.IP_COURSE_HOME = process.env.IP_COURSE_TEST_HOME || "/nonexistent/ip-course-test-home";
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {spawnSync} from "node:child_process";

const root = path.resolve(import.meta.dirname, "..");
const validator = path.join(root, "scripts", "validate_chapter_boundary.py");

function validate(html) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-chapter-boundary-"));
  const file = path.join(dir, "index.html");
  fs.writeFileSync(file, html);
  return spawnSync("python3", [validator, "--composition", file], {encoding: "utf8"});
}

test("chapter title interval contains only its signature sting", () => {
  const result = validate(`
    <main data-duration="12.6">
      <section data-chapter-title-broll data-start="0" data-duration="2.6"></section>
      <section class="caption" data-start="2.8" data-duration="1"></section>
      <audio data-chapter-sting data-start="0" data-duration="0.72"></audio>
      <audio data-narration-track data-start="2.6" data-duration="10"></audio>
    </main>`);
  assert.equal(result.status, 0, result.stderr);
});

test("validator rejects narration or captions over the chapter title", () => {
  const narration = validate(`
    <main data-duration="10">
      <section data-chapter-title-broll data-start="0" data-duration="2.6"></section>
      <section class="caption" data-start="0.2" data-duration="1"></section>
      <audio data-chapter-sting data-start="0" data-duration="0.72"></audio>
      <audio data-narration-track data-start="0" data-duration="10"></audio>
    </main>`);
  assert.notEqual(narration.status, 0);
  assert.match(narration.stderr, /旁白|字幕|章节页/);
});

test("skill documents the A-roll screen shell as a required assembly structure", () => {
  const text = fs.readFileSync(path.join(root, "references", "visual-system.md"), "utf8");
  assert.match(text, /A-roll.*外层.*paper.*内层.*stage/s);
  assert.match(text, /禁止.*全屏.*铺底/s);
});

test("validator rejects an A-roll scene that bypasses the locked screen shell", () => {
  const result = validate(`
    <main data-duration="12.6">
      <section data-chapter-title-broll data-start="0" data-duration="2.6"></section>
      <section data-aroll-scene data-start="4" data-duration="3"><img src="raw.png"></section>
      <audio data-chapter-sting data-start="0" data-duration="0.72"></audio>
      <audio data-narration-track data-start="2.6" data-duration="10"></audio>
    </main>`);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /画面背景|屏幕背景/);
});
