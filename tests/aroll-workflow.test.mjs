process.env.IP_COURSE_HOME = process.env.IP_COURSE_TEST_HOME || "/nonexistent/ip-course-test-home";
import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {spawnSync} from "node:child_process";

const root = path.resolve(import.meta.dirname, "..");
const profile = path.join(root, "assets/presets/aroll-profile.json");

function run(script, args) {
  return spawnSync("python3", [path.join(root, "scripts", script), ...args], {
    encoding: "utf8",
  });
}

function fixture(overrides = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-aroll-"));
  const candidateDir = path.join(dir, "assets/arroll/candidates");
  const cropDir = path.join(candidateDir, "crops");
  fs.mkdirSync(cropDir, {recursive: true});
  const asset = path.join(candidateDir, "login-f1.png");
  fs.writeFileSync(asset, "candidate-image");
  const crops = {
    full: asset,
    face: path.join(cropDir, "login-f1-face.png"),
    screenLeftEye: path.join(cropDir, "login-f1-left-eye.png"),
    screenRightEye: path.join(cropDir, "login-f1-right-eye.png"),
  };
  for (const file of Object.values(crops).slice(1)) fs.writeFileSync(file, "crop");
  const assetHash = crypto.createHash("sha256").update(fs.readFileSync(asset)).digest("hex");
  const candidate = {
    candidateId: "login-f1-v1",
    sequenceId: "login-checkpoint",
    beatId: "beat-01",
    assetPath: asset,
    assetHash,
    durationSeconds: 4.2,
    narrationCue: "选择自己的账号",
    actorAction: "人物伸手选择账号",
    gazeTarget: "账号列表",
    propState: "账号处于待选状态",
    crops,
    identityChecks: {
      screenLeftEyeMatches: "pass",
      screenRightEyeMatches: "pass",
      featureDrift: false,
      earsCorrect: "pass",
      hairCorrect: "pass",
      clothingCorrect: "pass",
      handsValid: "pass",
    },
    continuityChecks: {
      sameSceneWorld: "pass",
      sameCameraDirection: "pass",
      propStateInherited: "pass",
    },
    status: "REVIEW",
    ...overrides,
  };
  const manifest = {
    schemaVersion: 1,
    projectId: "demo",
    candidateRoot: candidateDir,
    approvedRoot: path.join(dir, "assets/arroll/approved"),
    sequences: [{
      id: "login-checkpoint",
      worldLockId: "login-hall-v1",
      beats: [{
        id: "beat-01",
        role: "action",
        candidateId: candidate.candidateId,
        narrationCue: candidate.narrationCue,
        actorAction: candidate.actorAction,
        gazeTarget: candidate.gazeTarget,
        propState: candidate.propState,
        durationSeconds: candidate.durationSeconds,
      }],
    }],
    candidates: [candidate],
    approvals: {},
  };
  const manifestPath = path.join(dir, "aroll-manifest.json");
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));
  return {dir, asset, manifestPath};
}

test("A-roll profile defines review cadence and a hard still limit", () => {
  const data = JSON.parse(fs.readFileSync(profile, "utf8"));
  assert.equal(data.cadence.targetActionBeatSeconds.min, 3);
  assert.equal(data.cadence.targetActionBeatSeconds.max, 5);
  assert.equal(data.cadence.softMaxStillSeconds, 6);
  assert.equal(data.cadence.hardMaxStillSeconds, 8);
  assert.equal(data.cadence.cameraMovementCountsAsActionChange, false);
});

test("A-roll validator leaves eye and anatomy judgement to human review", () => {
  const fx = fixture({
    identityChecks: {
      screenLeftEyeMatches: "pass",
      screenRightEyeMatches: "fail",
      featureDrift: true,
      earsCorrect: "pass",
      hairCorrect: "pass",
      clothingCorrect: "pass",
      handsValid: "pass",
    },
  });
  const result = run("validate_aroll.py", ["--manifest", fx.manifestPath, "--profile", profile, "--mode", "review"]);
  assert.equal(result.status, 0, result.stderr);
  const data = JSON.parse(fs.readFileSync(profile, "utf8"));
  assert.equal(data.automatedValidation.structuralOnly, true);
  assert.equal(data.automatedValidation.semanticVisualJudgement, false);
});

test("A-roll validator blocks a still longer than the hard limit", () => {
  const fx = fixture({durationSeconds: 8.1});
  const result = run("validate_aroll.py", ["--manifest", fx.manifestPath, "--profile", profile, "--mode", "review"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /8\.1|最长|时长/);
});

test("A-roll review contains full frame, face, both eyes, narration, action and duration", () => {
  const fx = fixture();
  const output = path.join(fx.dir, "review/index.html");
  const result = run("build_aroll_review.py", ["--manifest", fx.manifestPath, "--profile", profile, "--output", output]);
  assert.equal(result.status, 0, result.stderr);
  const html = fs.readFileSync(output, "utf8");
  assert.match(html, /login-f1-v1/);
  assert.match(html, /完整画面/);
  assert.match(html, /面部/);
  assert.match(html, /画面左眼/);
  assert.match(html, /画面右眼/);
  assert.match(html, /选择自己的账号/);
  assert.match(html, /人物伸手选择账号/);
  assert.match(html, /4\.2/);
  assert.match(html, /data-aroll-paper/);
  assert.match(html, /data-aroll-stage/);
  assert.match(html, /data-subtitle-safe-zone/);
  assert.equal((html.match(/<img /g) || []).length, 4);
});

test("A-roll validator binds sequences to the approved chapter background and cast hashes", () => {
  const fx = fixture();
  const registry = path.join(root, "assets/character-reference/registry.json");
  const host = JSON.parse(fs.readFileSync(registry, "utf8")).characters.find((x) => x.characterId === "ip-host");
  const environment = path.join(fx.dir, "environment-cast-plan.json");
  fs.writeFileSync(environment, JSON.stringify({status: "APPROVED", chapters: [{
    chapterId: "01", background: {backgroundId: "office-v1"},
    cast: [{characterId: "ip-host", version: host.version, referenceHash: host.sha256}],
  }]}));
  const manifest = JSON.parse(fs.readFileSync(fx.manifestPath, "utf8"));
  manifest.environmentCastPlan = environment;
  manifest.characterRegistry = registry;
  manifest.sequences[0].chapterId = "01";
  manifest.sequences[0].backgroundId = "wrong-background";
  manifest.sequences[0].castReferences = [{characterId: "ip-host", version: host.version, referenceHash: host.sha256}];
  fs.writeFileSync(fx.manifestPath, JSON.stringify(manifest));
  const result = run("validate_aroll.py", ["--manifest", fx.manifestPath, "--profile", profile, "--mode", "review"]);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /背景|backgroundId|office-v1/);
});

test("only a passing, explicitly approved candidate can be promoted and used by preview", () => {
  const fx = fixture();
  const before = run("validate_aroll.py", ["--manifest", fx.manifestPath, "--profile", profile, "--mode", "preview"]);
  assert.notEqual(before.status, 0);
  assert.match(before.stderr, /未批准|approved/i);

  const promoted = run("promote_aroll.py", [
    "--manifest", fx.manifestPath,
    "--profile", profile,
    "--candidate-id", "login-f1-v1",
    "--approved-by", "user",
  ]);
  assert.equal(promoted.status, 0, promoted.stderr);
  const data = JSON.parse(fs.readFileSync(fx.manifestPath, "utf8"));
  const candidate = data.candidates[0];
  assert.equal(candidate.status, "APPROVED");
  assert.ok(fs.existsSync(candidate.approvedAssetPath));
  assert.equal(data.approvals["login-f1-v1"].assetHash, candidate.assetHash);

  const after = run("validate_aroll.py", ["--manifest", fx.manifestPath, "--profile", profile, "--mode", "preview"]);
  assert.equal(after.status, 0, after.stderr);
});
