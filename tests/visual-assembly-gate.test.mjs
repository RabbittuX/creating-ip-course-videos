process.env.IP_COURSE_HOME = process.env.IP_COURSE_TEST_HOME || "/nonexistent/ip-course-test-home";
import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {spawnSync} from "node:child_process";

const root = path.resolve(import.meta.dirname, "..");
const run = (args) => spawnSync("python3", [path.join(root, "scripts", "validate_visual_assembly.py"), ...args], {encoding: "utf8"});
const sha = (file) => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");

function fixture({badAroll = false, badBroll = false} = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "visual-assembly-"));
  const aroll = path.join(dir, "aroll.html");
  const template = path.join(dir, "template.html");
  const broll = path.join(dir, "broll.html");
  fs.writeFileSync(aroll, badAroll
    ? `<div style="background:#252b31"><img style="position:absolute;inset:-18px;object-fit:cover"></div>`
    : `<main data-aroll-paper style="background:#f8f7f6"><section data-aroll-stage style="left:72px;right:72px;top:70px;height:820px;background:#fdfaf4"><img data-aroll-artwork></section></main>`);
  fs.writeFileSync(template, `<template><main class="deck"><section class="grid"><article data-state-item class="card"></article></section></main></template>`);
  fs.writeFileSync(broll, badBroll
    ? `<template><main class="generic-panel"><section class="same-layout"></section></main></template>`
    : fs.readFileSync(template));
  const manifest = path.join(dir, "visual-assembly.json");
  fs.writeFileSync(manifest, JSON.stringify({schemaVersion: 1, status: "READY",
    fixedAroll: [
      {role: "opening-title", sourcePath: path.join(root, "assets/arroll/fixed/opening-title.html")},
      {role: "opening-transition", sourcePath: path.join(root, "assets/arroll/fixed/opening-transition.html")},
    ],
    arollScenes: [{sceneId: "a1", compositionPath: aroll}],
    brollScenes: [{sceneId: "b1", designOrigin: "template", templateSourcePath: template, compositionPath: broll, templateSourceHash: sha(template)}],
  }));
  return manifest;
}

test("visual assembly rejects fullscreen dark A-roll without the locked paper shell", () => {
  const result = run(["--manifest", fixture({badAroll: true})]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /A-roll|aroll-stage|纸张外壳/);
});

test("visual assembly rejects generic B-roll that does not preserve the registered template structure", () => {
  const result = run(["--manifest", fixture({badBroll: true})]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /B-roll|模板结构/);
});

test("visual assembly accepts locked A-roll, exact fixed assets, and structurally derived B-roll", () => {
  const result = run(["--manifest", fixture()]);
  assert.equal(result.status, 0, result.stderr);
});
