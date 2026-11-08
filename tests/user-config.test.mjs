import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {spawnSync} from "node:child_process";

const root = path.resolve(import.meta.dirname, "..");
const placeholder = path.join(root, "assets/ip-reference/host-front.png");

function run(script, args, home, extraEnv = {}) {
  return spawnSync("python3", [path.join(root, "scripts", script), ...args], {
    encoding: "utf8",
    env: {...process.env, IP_COURSE_HOME: home, DOUBAO_APPID: "", DOUBAO_TOKEN: "", ...extraEnv},
  });
}

function configuredHome() {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-home-"));
  const img = path.join(home, "src");
  fs.mkdirSync(img);
  fs.copyFileSync(placeholder, path.join(img, "front.png"));
  fs.copyFileSync(placeholder, path.join(img, "cat.png"));
  const config = JSON.parse(fs.readFileSync(path.join(root, "config.example.json"), "utf8"));
  config.host.images = {"host-front": path.join(img, "front.png")};
  config.host.identityInvariants = ["橙色身体"];
  config.extraCharacters[0].images = {mascot: path.join(img, "cat.png")};
  config.extraCharacters[0].identityInvariants = ["小猫"];
  config.tts.voiceType = "test_voice_id";
  config.tts.ratePercent = 12;
  config.loudness = {integratedLufs: -16, integratedToleranceLu: 1};
  fs.writeFileSync(path.join(home, "config.json"), JSON.stringify(config));
  return home;
}

test("setup --init writes a template and never overwrites an existing config", () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-home-"));
  assert.equal(run("setup_config.py", ["--init"], home).status, 0);
  assert.ok(fs.existsSync(path.join(home, "config.json")));
  fs.writeFileSync(path.join(home, "config.json"), "{\"keep\":1}");
  run("setup_config.py", ["--init"], home);
  assert.equal(fs.readFileSync(path.join(home, "config.json"), "utf8"), "{\"keep\":1}");
});

test("setup rejects an unfilled template", () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-home-"));
  run("setup_config.py", ["--init"], home);
  const result = run("setup_config.py", [], home);
  assert.equal(result.status, 2);
  assert.match(result.stderr, /图片不存在|host-front/);
});

test("setup builds a hash-locked registry and fills every template slot", () => {
  const home = configuredHome();
  const result = run("setup_config.py", [], home);
  assert.equal(result.status, 0, result.stderr);
  const registry = JSON.parse(fs.readFileSync(path.join(home, "character-reference/registry.json"), "utf8"));
  assert.deepEqual(registry.characters.map((x) => x.characterId), ["ip-host", "mascot"]);
  const slots = JSON.parse(fs.readFileSync(path.join(root, "assets/character-slots.json"), "utf8")).slots;
  for (const {slot} of slots) assert.ok(fs.existsSync(path.join(home, "ip-reference", `${slot}.png`)), slot);
  assert.match(result.stdout, /DOUBAO_APPID/);
});

test("init_project uses the user registry and copies slot images into the project", () => {
  const home = configuredHome();
  run("setup_config.py", [], home);
  const project = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-project-"));
  const result = run("init_project.py", ["--root", project, "--project-id", "p", "--chapters", "01"], home);
  assert.equal(result.status, 0, result.stderr);
  const manifest = JSON.parse(fs.readFileSync(path.join(project, "project.json"), "utf8"));
  assert.equal(manifest.characterRegistry, fs.realpathSync(path.join(home, "character-reference/registry.json")));
  assert.ok(fs.existsSync(path.join(project, "assets/ip-reference/host-explain.png")));
  assert.doesNotMatch(result.stdout, /示例占位/);
});

test("init_project without setup falls back to the placeholder and says so", () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-project-"));
  const result = run("init_project.py", ["--root", project, "--project-id", "p", "--chapters", "01"], "/nonexistent/ip-course-home");
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /示例占位/);
});

test("TTS reads voice and rate from user config and never prints credentials", () => {
  const home = configuredHome();
  const text = path.join(home, "ch.txt");
  fs.writeFileSync(text, "第一章口播。");
  const result = run("tts_doubao.py", ["--text-file", text, "--output", path.join(home, "o.wav"), "--dry-run"], home, {DOUBAO_TOKEN: "secret-token-xyz"});
  assert.equal(result.status, 0, result.stderr);
  const body = JSON.parse(result.stdout);
  assert.equal(body.audio.voice_type, "test_voice_id");
  assert.equal(body.audio.speed_ratio, 1.12);
  assert.doesNotMatch(result.stdout, /secret-token-xyz/);
});

test("TTS refuses to run without a configured voice", () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-home-"));
  const text = path.join(home, "ch.txt");
  fs.writeFileSync(text, "口播");
  const result = run("tts_doubao.py", ["--text-file", text, "--output", path.join(home, "o.wav")], home);
  assert.equal(result.status, 2);
  assert.match(result.stderr, /voiceType/);
});

test("loudness targets merge user config over skill defaults", () => {
  const home = configuredHome();
  const code = "import json,user_config as u;print(json.dumps(u.audio_profile()['loudness']))";
  const result = spawnSync("python3", ["-c", code], {cwd: path.join(root, "scripts"), encoding: "utf8", env: {...process.env, IP_COURSE_HOME: home}});
  const loud = JSON.parse(result.stdout);
  assert.equal(loud.integratedLufs, -16);
  assert.equal(loud.truePeakCeilingDbtp, -0.3);
});

test("skill ships no personal assets or tuning values", () => {
  const files = spawnSync("git", ["ls-files", "--others", "--cached", "--exclude-standard"], {cwd: root, encoding: "utf8"}).stdout.trim().split("\n").filter(Boolean);
  const list = files.length > 1 ? files : fs.readdirSync(root, {recursive: true}).map(String);
  const banned = /zh_male_|_bigtts|\/Users\/|cat-ear|白发猫耳|四角星|-10\.3/;
  for (const rel of list) {
    const full = path.join(root, rel);
    if (!fs.statSync(full).isFile() || !/\.(md|json|html|js|mjs|py|yaml|sh)$/.test(rel) || rel.startsWith("tests/")) continue;
    assert.doesNotMatch(fs.readFileSync(full, "utf8"), banned, rel);
  }
  const images = fs.readdirSync(path.join(root, "assets/ip-reference")).sort();
  assert.deepEqual(images, ["host-front.png", "transparent.png"]);
});
