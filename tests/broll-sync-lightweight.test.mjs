process.env.IP_COURSE_HOME = process.env.IP_COURSE_TEST_HOME || "/nonexistent/ip-course-test-home";
import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import vm from "node:vm";
import {spawnSync} from "node:child_process";
import {prepareReviewArtifacts, promoteArollFixture, seedGate, setArtifactStatus, setCanonicalNarration, writeAudioReady} from "./helpers/workflow-fixture.mjs";

const root = path.resolve(import.meta.dirname, "..");
const run = (script, args) => spawnSync("python3", [path.join(root, "scripts", script), ...args], {encoding: "utf8"});
const sha = (file) => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");

test("mapping builder stores source ranges while B-roll summaries are created", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "broll-map-build-"));
  const draft = path.join(dir, "draft.json");
  const output = path.join(dir, "map.json");
  fs.writeFileSync(draft, JSON.stringify({chapterId: "01", narration: "123456，然后讲 abcdef。", items: [
    {itemId: "one", label: "345", sourceText: "123456"},
    {itemId: "two", label: "cde", sourceText: "abcdef"},
  ]}));
  const result = run("build_broll_narration_map.py", ["--input", draft, "--output", output]);
  assert.equal(result.status, 0, result.stderr);
  const data = JSON.parse(fs.readFileSync(output, "utf8"));
  assert.deepEqual(data.items.map((x) => x.switchAtChar), [0, 11]);
  assert.deepEqual(data.items.map((x) => x.sourceCharEnd), [6, 17]);
  assert.deepEqual(data.items.map((x) => x.label), ["345", "cde"]);
});

test("resolver uses character offsets and keeps the final item active until its source span ends", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "broll-offset-resolve-"));
  const mapping = path.join(dir, "map.json");
  const alignment = path.join(dir, "alignment.json");
  const audio = path.join(dir, "narration.m4a");
  const output = path.join(dir, "timeline.json");
  fs.writeFileSync(audio, "audio-v1");
  fs.writeFileSync(mapping, JSON.stringify({narration: "123456abcdef", items: [
    {itemId: "one", label: "345", sourceCharStart: 0, sourceCharEnd: 6, switchAtChar: 0, triggerText: "123"},
    {itemId: "two", label: "cde", sourceCharStart: 6, sourceCharEnd: 12, switchAtChar: 6, triggerText: "abc"},
  ]}));
  fs.writeFileSync(alignment, JSON.stringify({audioHash: sha(audio), tokens: [
    {id: "t1", text: "123", charStart: 0, charEnd: 3, startMs: 100, endMs: 300},
    {id: "t2", text: "456", charStart: 3, charEnd: 6, startMs: 300, endMs: 650},
    {id: "t3", text: "abc", charStart: 6, charEnd: 9, startMs: 700, endMs: 900},
    {id: "t4", text: "def", charStart: 9, charEnd: 12, startMs: 900, endMs: 1400},
  ]}));
  const result = run("resolve_broll_timeline.py", ["--map", mapping, "--alignment", alignment, "--audio", audio, "--output", output]);
  assert.equal(result.status, 0, result.stderr);
  const timeline = JSON.parse(fs.readFileSync(output, "utf8"));
  assert.deepEqual(timeline.items.map((x) => x.activeAtMs), [100, 700]);
  assert.deepEqual(timeline.items.map((x) => x.completeAtMs), [700, 1400]);
  assert.equal(timeline.items[1].triggerTokenId, "t3");
  assert.equal(timeline.items[1].sourceEndTokenId, "t4");
});

test("resolver completes the last item of each B-roll scene at that scene narration end", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "broll-scene-boundary-"));
  const mapping = path.join(dir, "map.json");
  const alignment = path.join(dir, "alignment.json");
  const audio = path.join(dir, "narration.m4a");
  const output = path.join(dir, "timeline.json");
  fs.writeFileSync(audio, "audio-v1");
  fs.writeFileSync(mapping, JSON.stringify({narration: "甲乙中间丙丁", items: [
    {sceneId: "a", itemId: "one", sourceCharStart: 0, sourceCharEnd: 2, switchAtChar: 0, triggerText: "甲"},
    {sceneId: "b", itemId: "two", sourceCharStart: 4, sourceCharEnd: 6, switchAtChar: 4, triggerText: "丙"},
  ]}));
  fs.writeFileSync(alignment, JSON.stringify({audioHash: sha(audio), tokens: [
    {id: "t1", text: "甲乙", charStart: 0, charEnd: 2, startMs: 100, endMs: 500},
    {id: "t2", text: "丙丁", charStart: 4, charEnd: 6, startMs: 1500, endMs: 1900},
  ]}));
  const result = run("resolve_broll_timeline.py", ["--map", mapping, "--alignment", alignment, "--audio", audio, "--output", output]);
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(fs.readFileSync(output, "utf8")).items.map((x) => x.completeAtMs), [500, 1900]);
});

test("shared progress controller derives gray yellow green states from one timeline", () => {
  const source = fs.readFileSync(path.join(root, "assets/broll/broll-progress-controller.js"), "utf8");
  const context = {globalThis: {}};
  vm.runInNewContext(source, context);
  const controller = context.globalThis.BrollProgressController;
  const timeline = [
    {itemId: "one", activeAtMs: 100, completeAtMs: 700},
    {itemId: "two", activeAtMs: 700, completeAtMs: 1400},
  ];
  assert.deepEqual(JSON.parse(JSON.stringify(controller.stateAt(timeline, 50).map((x) => x.state))), ["unvisited", "unvisited"]);
  assert.deepEqual(JSON.parse(JSON.stringify(controller.stateAt(timeline, 500).map((x) => x.state))), ["active", "unvisited"]);
  assert.deepEqual(JSON.parse(JSON.stringify(controller.stateAt(timeline, 900).map((x) => x.state))), ["completed", "active"]);
  assert.deepEqual(JSON.parse(JSON.stringify(controller.stateAt(timeline, 1500).map((x) => x.state))), ["completed", "completed"]);
  assert.deepEqual(JSON.parse(JSON.stringify(controller.layoutFor(
    {left: 10, top: 20},
    {left: 110, top: 120, right: 310, bottom: 320, width: 200, height: 200},
    {width: 60, height: 100},
  ))), {focus: {left: 100, top: 100, width: 200, height: 200}, pointer: {left: 224, top: 184}});
});

test("shared controller updates state whenever HyperFrames seeks the GSAP timeline", () => {
  const source = fs.readFileSync(path.join(root, "assets/broll/broll-progress-controller.js"), "utf8");
  const context = {globalThis: {}};
  vm.runInNewContext(source, context);
  const node = {dataset: {itemId: "one"}, style: {}, getBoundingClientRect: () => ({left: 0, top: 0, right: 100, bottom: 100, width: 100, height: 100})};
  const rootNode = {
    dataset: {},
    querySelectorAll: () => [node],
    querySelector: (selector) => selector.includes("one") ? node : null,
    getBoundingClientRect: () => ({left: 0, top: 0}),
  };
  let current = 0;
  let callback;
  const timeline = {
    time: () => current,
    eventCallback: (_name, value) => value === undefined ? callback : (callback = value),
  };
  context.globalThis.BrollProgressController.bindGsap(rootNode, [{itemId: "one", activeAtMs: 500, completeAtMs: 1000}], timeline);
  assert.equal(node.dataset.stateRole, "unvisited");
  current = 0.7;
  callback();
  assert.equal(node.dataset.stateRole, "active");
  current = 1.1;
  callback();
  assert.equal(node.dataset.stateRole, "completed");
  assert.equal(rootNode.dataset.brollProgressRuntime, "bound");
});

test("every state-progress template requires the shared narration timeline driver", () => {
  const registry = JSON.parse(fs.readFileSync(path.join(root, "assets/broll/template-registry.json"), "utf8"));
  const stateTemplates = registry.templates.filter((x) => x.stateProgress);
  assert.ok(stateTemplates.length > 0);
  for (const item of stateTemplates) {
    assert.equal(item.requiresNarrationMap, true, item.id);
    assert.equal(item.requiresResolvedTimeline, true, item.id);
    assert.equal(item.stateDriver, "broll-progress-controller", item.id);
  }
});

test("runtime wiring embeds the resolved scene timeline and binds controller updates to GSAP seek", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "broll-runtime-wire-"));
  const composition = path.join(dir, "scene.html");
  const timeline = path.join(dir, "timeline.json");
  fs.writeFileSync(composition, `<template><div id="root" data-composition-id="scene-a"><section data-state-item data-item-id="one"></section></div><script>window.__timelines=window.__timelines||{};const tl=gsap.timeline({paused:true});window.__timelines["scene-a"]=tl;</script></template>`);
  fs.writeFileSync(timeline, JSON.stringify({items: [
    {sceneId: "scene-a", itemId: "one", activeAtMs: 1200, completeAtMs: 1800},
    {sceneId: "scene-b", itemId: "other", activeAtMs: 2200, completeAtMs: 2600},
  ]}));
  const result = run("wire_broll_progress.py", ["--composition", composition, "--timeline", timeline, "--scene-id", "scene-a", "--origin-ms", "1000"]);
  assert.equal(result.status, 0, result.stderr);
  const html = fs.readFileSync(composition, "utf8");
  assert.match(html, /data-broll-progress-wired="scene-a"/);
  assert.match(html, /BrollProgressController\.bindGsap/);
  assert.match(html, /"itemId":\s*"one"/);
  assert.doesNotMatch(html, /"itemId":\s*"other"/);
});

test("project sync preparation builds narration maps automatically from the approved visual outline", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "broll-auto-map-"));
  const project = path.join(dir, "project");
  assert.equal(run("init_project.py", ["--root", project, "--project-id", "demo", "--chapters", "01"]).status, 0);
  prepareReviewArtifacts(project);
  setArtifactStatus(project, "environment-cast-plan.json", "APPROVED");
  promoteArollFixture(project);
  const outlinePath = path.join(project, "planning", "visual-outline.json");
  fs.writeFileSync(outlinePath, JSON.stringify({schemaVersion: 2, status: "APPROVED", chapters: [{
    chapterId: "01",
    narration: "先说输入，再说输出。",
    scenes: [{sceneId: "flow", type: "B-roll", progressMode: "narration-driven", items: [
      {itemId: "input", label: "输入", sourceText: "先说输入"},
      {itemId: "output", label: "输出", sourceText: "再说输出"},
    ]}],
  }]}));
  const result = run("prepare_broll_sync.py", ["--project-root", project]);
  assert.equal(result.status, 0, result.stderr);
  const mapping = JSON.parse(fs.readFileSync(path.join(project, "chapters", "01", "planning", "broll-narration-map.json"), "utf8"));
  assert.deepEqual(mapping.items.map((x) => [x.sceneId, x.itemId, x.switchAtChar]), [["flow", "input", 0], ["flow", "output", 5]]);
});

test("BROLL_SYNC_READY is blocked until lightweight map timeline and runtime evidence exist", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "broll-sync-gate-"));
  const project = path.join(dir, "project");
  assert.equal(run("init_project.py", ["--root", project, "--project-id", "demo", "--chapters", "01"]).status, 0);
  prepareReviewArtifacts(project);
  setArtifactStatus(project, "environment-cast-plan.json", "APPROVED");
  promoteArollFixture(project);
  const approvals = path.join(project, "approvals.json");
  for (const [gate, build] of [["environment-cast", "env"], ["visual-outline", "outline"], ["aroll-images", "aroll"]]) seedGate(approvals, "01", gate, build);
  fs.writeFileSync(path.join(project, "planning", "visual-outline.json"), JSON.stringify({status: "APPROVED", chapters: [{chapterId: "01", narration: "先说第一项。", scenes: [{
    sceneId: "flow", type: "B-roll", progressMode: "narration-driven", sourceText: "先说第一项。", sourceCharStart: 0, sourceCharEnd: 6, plannedDurationSeconds: 1,
    items: [{itemId: "one", label: "第一项", sourceText: "先说第一项"}],
  }]}]}));
  setCanonicalNarration(project, "01", "先说第一项。");
  writeAudioReady(project, "01", "先说第一项。");
  assert.equal(run("approval_gate.py", ["mark-ready", "--file", approvals, "--chapter", "01", "--milestone", "audio", "--build-id", "audio", "--project-root", project]).status, 0);
  const result = run("approval_gate.py", ["mark-ready", "--file", approvals, "--chapter", "01", "--milestone", "broll-sync", "--build-id", "sync", "--project-root", project]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /映射|时间线|运行时|visual-outline|B-roll/);
});

test("every enabled B-roll template explicitly declares static or narration-driven progress", () => {
  const registry = JSON.parse(fs.readFileSync(path.join(root, "assets/broll/template-registry.json"), "utf8"));
  for (const item of registry.templates.filter((x) => x.enabled)) {
    assert.ok(["static", "narration-driven"].includes(item.progressMode), item.id);
    assert.equal(Boolean(item.stateProgress), item.progressMode === "narration-driven", item.id);
  }
});

test("complete lightweight sync artifacts unlock BROLL_SYNC_READY", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "broll-sync-ready-"));
  const project = path.join(dir, "project");
  assert.equal(run("init_project.py", ["--root", project, "--project-id", "demo", "--chapters", "01"]).status, 0);
  prepareReviewArtifacts(project);
  setArtifactStatus(project, "environment-cast-plan.json", "APPROVED");
  promoteArollFixture(project);
  const composition = path.join(project, "chapters", "01", "broll", "flow.html");
  fs.writeFileSync(composition, `<template><div id="root" data-composition-id="flow"><section data-state-item data-item-id="one"></section></div><script>window.__timelines=window.__timelines||{};const tl=gsap.timeline({paused:true});window.__timelines["flow"]=tl;</script></template>`);
  fs.writeFileSync(path.join(project, "planning", "visual-outline.json"), JSON.stringify({status: "APPROVED", chapters: [{chapterId: "01", narration: "先说第一项。", scenes: [{
    sceneId: "flow", type: "B-roll", progressMode: "narration-driven", compositionPath: "chapters/01/broll/flow.html", sourceText: "先说第一项。", sourceCharStart: 0, sourceCharEnd: 6, plannedDurationSeconds: 1,
    items: [{itemId: "one", label: "第一项", sourceText: "先说第一项"}],
  }]}]}));
  setCanonicalNarration(project, "01", "先说第一项。");
  assert.equal(run("prepare_broll_sync.py", ["--project-root", project]).status, 0);
  const {audio, alignment} = writeAudioReady(project, "01", "先说第一项。");
  const map = path.join(project, "chapters", "01", "planning", "broll-narration-map.json");
  const timeline = path.join(project, "chapters", "01", "timing", "broll-state-timeline.json");
  assert.equal(run("resolve_broll_timeline.py", ["--map", map, "--alignment", alignment, "--audio", audio, "--output", timeline]).status, 0);
  assert.equal(run("wire_broll_progress.py", ["--composition", composition, "--timeline", timeline, "--scene-id", "flow"]).status, 0);
  const candidateRoot = path.join(project, "assets/broll/candidates");
  const approvedRoot = path.join(project, "assets/broll/approved");
  const candidateSource = path.join(candidateRoot, "flow.html");
  const approvedSource = path.join(approvedRoot, "flow.html");
  fs.copyFileSync(composition, candidateSource);
  fs.copyFileSync(composition, approvedSource);
  const sourceHash = sha(candidateSource);
  const manifest = {
    schemaVersion: 1, projectId: "demo", candidateRoot, approvedRoot,
    candidates: [{
      candidateId: "flow-v1", chapterId: "01", sceneId: "flow", templateId: "flow-v1", version: 1,
      family: "workflow", sourcePath: candidateSource, sourceHash, approvedSourcePath: approvedSource,
      sourceMode: "schematic", narrationCue: "先说第一项。", cueWindow: {start: 0, end: 1},
      requiredInteractions: [], visualEvents: [], stateProgress: true, progressMode: "narration-driven",
      narrationMapPath: map, resolvedTimelinePath: timeline, stateDriver: "broll-progress-controller",
      stateTimeline: [{time: 0, active: null, completed: ["one"], unvisited: [], progress: 1}],
      inspection: {canvas: {width: 1920, height: 1080}, sampledFrames: []},
      humanChecks: {semanticAccuracy: "pass"}, status: "APPROVED",
      registryEntry: {id: "flow-v1", version: 1, mode: "library", family: "workflow", minItems: 1, maxItems: 3, minDurationSeconds: 0, maxDurationSeconds: 3, supportedInteractions: [], progressMode: "narration-driven", stateDriver: "broll-progress-controller"},
    }],
    approvals: {"flow-v1": {sourceHash}}, selectionAudit: {uses: []},
  };
  fs.writeFileSync(path.join(project, "planning/broll-manifest.json"), JSON.stringify(manifest));
  const approvedOutline = JSON.parse(fs.readFileSync(path.join(project, "planning/visual-outline.json"), "utf8"));
  approvedOutline.chapters[0].scenes[0].compositionPath = approvedSource;
  approvedOutline.chapters[0].scenes[0].compositionHash = sha(approvedSource);
  fs.writeFileSync(path.join(project, "planning/visual-outline.json"), JSON.stringify(approvedOutline));
  const approvals = path.join(project, "approvals.json");
  for (const [gate, build] of [["environment-cast", "env"], ["visual-outline", "outline"], ["aroll-images", "aroll"]]) seedGate(approvals, "01", gate, build);
  assert.equal(run("approval_gate.py", ["mark-ready", "--file", approvals, "--chapter", "01", "--milestone", "audio", "--build-id", "audio", "--project-root", project]).status, 0);
  const ready = run("approval_gate.py", ["mark-ready", "--file", approvals, "--chapter", "01", "--milestone", "broll-sync", "--build-id", "sync", "--project-root", project]);
  assert.equal(ready.status, 0, ready.stderr);
  const state = JSON.parse(fs.readFileSync(approvals, "utf8"));
  assert.match(state.chapters["01"].milestones["broll-sync"].evidence.timelineHash, /^[a-f0-9]{64}$/);
  assert.equal(state.chapters["01"].state, "BROLL_SYNC_READY");
});
