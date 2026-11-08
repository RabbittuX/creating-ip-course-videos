process.env.IP_COURSE_HOME = process.env.IP_COURSE_TEST_HOME || "/nonexistent/ip-course-test-home";
import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {spawnSync} from "node:child_process";

const root = path.resolve(import.meta.dirname, "..");
const profile = path.join(root, "assets/presets/broll-profile.json");

function run(script, args) {
  return spawnSync("python3", [path.join(root, "scripts", script), ...args], {encoding: "utf8"});
}

function hash(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

function fixture(overrides = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-broll-"));
  const candidateRoot = path.join(dir, "assets/broll/candidates");
  const approvedRoot = path.join(dir, "assets/broll/approved");
  fs.mkdirSync(candidateRoot, {recursive: true});
  const sourcePath = path.join(candidateRoot, "route-v1.html");
  fs.writeFileSync(sourcePath, "<template><section>demo</section></template>");
  const narrationMapPath = path.join(dir, "broll-narration-map.json");
  const resolvedTimelinePath = path.join(dir, "broll-state-timeline.json");
  fs.writeFileSync(narrationMapPath, JSON.stringify({narration: "依次完成三个步骤", items: [
    {itemId: "step-01", sourceCharStart: 0, sourceCharEnd: 2, switchAtChar: 0, triggerText: "依次"},
    {itemId: "step-02", sourceCharStart: 2, sourceCharEnd: 4, switchAtChar: 2, triggerText: "完成"},
    {itemId: "step-03", sourceCharStart: 4, sourceCharEnd: 7, switchAtChar: 4, triggerText: "三个步骤"},
  ]}));
  fs.writeFileSync(resolvedTimelinePath, JSON.stringify({items: [
    {itemId: "step-01", activeAtMs: 1000, completeAtMs: 3000},
    {itemId: "step-02", activeAtMs: 3000, completeAtMs: 5000},
    {itemId: "step-03", activeAtMs: 5000, completeAtMs: 5500},
  ]}));
  const candidate = {
    candidateId: "route-v1",
    templateId: "route-v1",
    version: 1,
    family: "workflow",
    sourcePath,
    sourceHash: hash(sourcePath),
    sourceMode: "schematic",
    narrationCue: "依次完成三个步骤",
    cueWindow: {start: 0.5, end: 5.5},
    requiredInteractions: ["I01"],
    visualEvents: [
      {time: 1, target: "step-01"},
      {time: 3, target: "step-02"},
      {time: 5, target: "step-03"},
    ],
    stateProgress: true,
    progressMode: "narration-driven",
    narrationMapPath,
    resolvedTimelinePath,
    stateDriver: "broll-progress-controller",
    stateTimeline: [
      {time: 1, active: "step-01", completed: [], unvisited: ["step-02", "step-03"], progress: 0.2},
      {time: 3, active: "step-02", completed: ["step-01"], unvisited: ["step-03"], progress: 0.55},
      {time: 5, active: null, completed: ["step-01", "step-02", "step-03"], unvisited: [], progress: 1},
    ],
    inspection: {
      canvas: {width: 1920, height: 1080},
      sampledFrames: [
        {time: 0, textOverflowCount: 0, outOfBoundsCount: 0, focusMisalignedCount: 0, whiteFrame: false, focusVisible: true, stateColors: {active: "#e9a51a", completed: "#55d4b4", unvisited: "#71818e"}},
        {time: 5.9, textOverflowCount: 0, outOfBoundsCount: 0, focusMisalignedCount: 0, whiteFrame: false, focusVisible: false, stateColors: {completed: "#55d4b4"}},
      ],
    },
    humanChecks: {narrationStepSync: "pass", semanticAccuracy: "pass"},
    status: "REVIEW",
    registryEntry: {
      id: "route-v1", version: 1, mode: "library", enabled: true, family: "workflow",
      tags: ["workflow"], minItems: 1, maxItems: 4, minDurationSeconds: 3,
      maxDurationSeconds: 8, supportedInteractions: ["I01"],
      stateProgress: true, requiresNarrationMap: true, requiresResolvedTimeline: true,
      stateDriver: "broll-progress-controller", progressMode: "narration-driven",
    },
    ...overrides,
  };
  const manifest = {
    schemaVersion: 1,
    projectId: "demo",
    candidateRoot,
    approvedRoot,
    candidates: [candidate],
    approvals: {},
    selectionAudit: {
      functionalSceneCount: 4,
      uses: [
        {sceneId: "1", templateId: "a", family: "workflow", eligibleFamilyVariants: 3},
        {sceneId: "2", templateId: "a", family: "workflow", eligibleFamilyVariants: 3},
        {sceneId: "3", templateId: "b", family: "workflow", eligibleFamilyVariants: 3},
        {sceneId: "4", templateId: "c", family: "workflow", eligibleFamilyVariants: 3},
      ],
    },
  };
  const manifestPath = path.join(dir, "broll-manifest.json");
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  return {dir, manifestPath, sourcePath};
}

test("enabled B-roll templates declare enforceable duration, capacity and interactions", () => {
  const registry = JSON.parse(fs.readFileSync(path.join(root, "assets/broll/template-registry.json"), "utf8"));
  for (const item of registry.templates.filter((x) => x.enabled !== false)) {
    assert.ok(Number.isInteger(item.version) && item.version >= 1, item.id);
    assert.ok(Number.isFinite(item.minItems), item.id);
    assert.ok(Number.isFinite(item.maxItems), item.id);
    assert.ok(Number.isFinite(item.minDurationSeconds), item.id);
    assert.ok(Number.isFinite(item.maxDurationSeconds), item.id);
    assert.ok(Array.isArray(item.supportedInteractions), item.id);
  }
});

test("registered state-progress templates expose inspectable items and canonical state colors", () => {
  const registry = JSON.parse(fs.readFileSync(path.join(root, "assets/broll/template-registry.json"), "utf8"));
  const stateTemplates = registry.templates.filter((x) => x.enabled !== false && x.stateProgress === true);
  assert.ok(stateTemplates.length >= 5);
  for (const item of stateTemplates) {
    const source = fs.readFileSync(path.join(root, "assets/broll", item.source), "utf8").toLowerCase();
    assert.match(source, /data-state-item/, item.id);
    assert.match(source, /#e9a51a/, `${item.id} active`);
    assert.match(source, /#55d4b4/, `${item.id} completed`);
    assert.match(source, /#71818e/, `${item.id} unvisited`);
    assert.match(source, /data-state-finalized/, `${item.id} final marker`);
  }
});

test("selector enforces duration and required interaction", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-select-capability-"));
  const registry = {templates: [
    {id: "a", version: 1, mode: "library", enabled: true, family: "workflow", source: "a.html", tags: [], minItems: 1, maxItems: 3, minDurationSeconds: 3, maxDurationSeconds: 5, supportedInteractions: ["I01"], progressMode: "static"},
    {id: "b", version: 1, mode: "library", enabled: true, family: "workflow", source: "b.html", tags: [], minItems: 1, maxItems: 3, minDurationSeconds: 5, maxDurationSeconds: 8, supportedInteractions: ["I04"], progressMode: "static"},
  ]};
  const plan = {projectId: "demo", scenes: [{id: "s1", family: "workflow", itemCount: 2, durationSeconds: 6, requiredInteractions: ["I01"], progressMode: "static"}]};
  const registryPath = path.join(dir, "registry.json");
  const planPath = path.join(dir, "plan.json");
  fs.writeFileSync(registryPath, JSON.stringify(registry));
  fs.writeFileSync(planPath, JSON.stringify(plan));
  const result = run("select_broll.py", ["--project", planPath, "--registry", registryPath, "--output", path.join(dir, "lock.json")]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /duration|时长|interaction|交互/i);
});

test("selector never substitutes a static template for narration-driven B-roll", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-select-progress-"));
  const registry = {templates: [
    {id: "static", version: 1, mode: "library", enabled: true, family: "workflow", source: "static.html", tags: [], minItems: 1, maxItems: 3, minDurationSeconds: 3, maxDurationSeconds: 8, supportedInteractions: [], progressMode: "static"},
    {id: "driven", version: 1, mode: "library", enabled: true, family: "workflow", source: "driven.html", tags: [], minItems: 1, maxItems: 3, minDurationSeconds: 3, maxDurationSeconds: 8, supportedInteractions: [], progressMode: "narration-driven", stateProgress: true},
  ]};
  const plan = {projectId: "demo", scenes: [{id: "s1", family: "workflow", itemCount: 2, durationSeconds: 6, progressMode: "narration-driven"}]};
  const registryPath = path.join(dir, "registry.json");
  const planPath = path.join(dir, "plan.json");
  const output = path.join(dir, "lock.json");
  fs.writeFileSync(registryPath, JSON.stringify(registry));
  fs.writeFileSync(planPath, JSON.stringify(plan));
  const result = run("select_broll.py", ["--project", planPath, "--registry", registryPath, "--output", output]);
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(fs.readFileSync(output, "utf8")).selections[0].templateId, "driven");
});

test("selector rejects functional B-roll without an explicit progressMode", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-select-missing-progress-"));
  const registry = {templates: [{id: "static", version: 1, mode: "library", enabled: true, family: "concept", source: "static.html", tags: [], minItems: 1, maxItems: 3, minDurationSeconds: 3, maxDurationSeconds: 8, supportedInteractions: [], progressMode: "static"}]};
  const plan = {projectId: "demo", scenes: [{id: "s1", family: "concept", itemCount: 2, durationSeconds: 6}]};
  const registryPath = path.join(dir, "registry.json");
  const planPath = path.join(dir, "plan.json");
  fs.writeFileSync(registryPath, JSON.stringify(registry));
  fs.writeFileSync(planPath, JSON.stringify(plan));
  const result = run("select_broll.py", ["--project", planPath, "--registry", registryPath, "--output", path.join(dir, "lock.json")]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /progressMode/);
});

test("selector puts three functional scenes between exact repeats when alternatives exist", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-select-gap-"));
  const templates = ["a", "b", "c", "d"].map((id) => ({
    id, version: 1, mode: "library", enabled: true, family: "workflow", source: `${id}.html`,
    tags: [], minItems: 1, maxItems: 3, minDurationSeconds: 3, maxDurationSeconds: 8,
    supportedInteractions: ["I01"], progressMode: "static",
  }));
  const plan = {projectId: "gap", scenes: Array.from({length: 8}, (_, i) => ({
    id: `s${i + 1}`, chapterId: "01", family: "workflow", itemCount: 2,
    durationSeconds: 6, requiredInteractions: ["I01"], progressMode: "static",
  }))};
  const registryPath = path.join(dir, "registry.json");
  const planPath = path.join(dir, "plan.json");
  const output = path.join(dir, "lock.json");
  fs.writeFileSync(registryPath, JSON.stringify({templates}));
  fs.writeFileSync(planPath, JSON.stringify(plan));
  const result = run("select_broll.py", ["--project", planPath, "--registry", registryPath, "--output", output]);
  assert.equal(result.status, 0, result.stderr);
  const ids = JSON.parse(fs.readFileSync(output, "utf8")).selections.map((x) => x.templateId);
  ids.forEach((id, index) => assert.equal(ids.slice(Math.max(0, index - 3), index).includes(id), false));
});

test("B-roll validator blocks layout defects, state rollback and end-state reset", () => {
  const fx = fixture({
    stateTimeline: [
      {time: 1, active: "step-02", completed: ["step-01"], unvisited: ["step-03"], progress: 0.5},
      {time: 3, active: "step-01", completed: [], unvisited: ["step-02", "step-03"], progress: 0.2},
      {time: 5, active: "step-03", completed: ["step-01", "step-02"], unvisited: [], progress: 0.9},
    ],
    inspection: {canvas: {width: 1920, height: 1080}, sampledFrames: [
      {time: 2, textOverflowCount: 1, outOfBoundsCount: 0, focusMisalignedCount: 1, whiteFrame: true},
    ]},
  });
  const result = run("validate_broll.py", ["--manifest", fx.manifestPath, "--profile", profile, "--mode", "review"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /文字溢出/);
  assert.match(result.stderr, /选中框|焦点/);
  assert.match(result.stderr, /白屏|白闪/);
  assert.match(result.stderr, /回跳|倒退|最终状态/);
});

test("B-roll validator independently enforces state colors and hides end focus", () => {
  const fx = fixture({inspection: {canvas: {width: 1920, height: 1080}, sampledFrames: [
    {time: 0, textOverflowCount: 0, outOfBoundsCount: 0, focusMisalignedCount: 0, whiteFrame: false, focusVisible: true, stateColors: {active: "#ffffff", completed: "#55d4b4", unvisited: "#71818e"}},
    {time: 5.9, textOverflowCount: 0, outOfBoundsCount: 0, focusMisalignedCount: 0, whiteFrame: false, focusVisible: true, stateColors: {completed: "#55d4b4"}},
  ]}});
  const result = run("validate_broll.py", ["--manifest", fx.manifestPath, "--profile", profile, "--mode", "review"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /颜色|黄色/);
  assert.match(result.stderr, /焦点|指针/);
});

test("state-progress B-roll cannot bypass narration mapping or the shared controller", () => {
  const fx = fixture({narrationMapPath: null, stateDriver: "manual-even-spacing"});
  const result = run("validate_broll.py", ["--manifest", fx.manifestPath, "--profile", profile, "--mode", "review"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /口播映射|broll-progress-controller|时间线/);
});

test("B-roll validator requires explicit progressMode and keeps it consistent with the registry", () => {
  const fx = fixture({progressMode: null});
  const result = run("validate_broll.py", ["--manifest", fx.manifestPath, "--profile", profile, "--mode", "review"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /progressMode/);
});

test("B-roll validator blocks narration mismatch and unverifiable real UI", () => {
  const fx = fixture({
    sourceMode: "real-ui",
    visualEvents: [{time: 6, target: "wrong-step"}],
    humanChecks: {narrationStepSync: "fail", semanticAccuracy: "pass"},
  });
  const result = run("validate_broll.py", ["--manifest", fx.manifestPath, "--profile", profile, "--mode", "review"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /口播|同步/);
  assert.match(result.stderr, /真实截图|溯源|real-ui/i);
});

test("validator warns when one template exceeds 40 percent with three eligible variants", () => {
  const fx = fixture();
  const result = run("validate_broll.py", ["--manifest", fx.manifestPath, "--profile", profile, "--mode", "review"]);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /40%|占比/);
});

test("only a passing explicitly approved B-roll candidate can be promoted and registered", () => {
  const fx = fixture();
  const registry = path.join(fx.dir, "registry.json");
  fs.writeFileSync(registry, JSON.stringify({schemaVersion: 1, templates: []}));
  const before = run("validate_broll.py", ["--manifest", fx.manifestPath, "--profile", profile, "--mode", "preview"]);
  assert.notEqual(before.status, 0);
  assert.match(before.stderr, /未批准|approved/i);
  const promoted = run("promote_broll.py", [
    "--manifest", fx.manifestPath, "--profile", profile, "--registry", registry,
    "--candidate-id", "route-v1", "--approved-by", "user",
  ]);
  assert.equal(promoted.status, 0, promoted.stderr);
  const manifest = JSON.parse(fs.readFileSync(fx.manifestPath, "utf8"));
  assert.equal(manifest.candidates[0].status, "APPROVED");
  assert.ok(fs.existsSync(manifest.candidates[0].approvedSourcePath));
  const entries = JSON.parse(fs.readFileSync(registry, "utf8")).templates;
  assert.equal(entries.length, 1);
  assert.equal(entries[0].id, "route-v1");
  assert.match(entries[0].source, /route-v1\.html$/);
  const after = run("validate_broll.py", ["--manifest", fx.manifestPath, "--profile", profile, "--mode", "preview"]);
  assert.equal(after.status, 0, after.stderr);
});

test("B-roll review page exposes animation source, keyframes, cue, IDs and issues", () => {
  const fx = fixture();
  const output = path.join(fx.dir, "review/index.html");
  const result = run("build_broll_review.py", ["--manifest", fx.manifestPath, "--profile", profile, "--output", output]);
  assert.equal(result.status, 0, result.stderr);
  const html = fs.readFileSync(output, "utf8");
  for (const term of ["route-v1", "workflow", "依次完成三个步骤", "关键帧", "动画预览", "状态时间线", "素材哈希"])
    assert.match(html, new RegExp(term));
  assert.match(html, /<iframe/);
});
