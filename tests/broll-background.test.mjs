process.env.IP_COURSE_HOME = process.env.IP_COURSE_TEST_HOME || "/nonexistent/ip-course-test-home";
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import {spawnSync} from "node:child_process";

const root = path.resolve(import.meta.dirname, "..");

test("every registered B-roll template uses the locked dark grid background", () => {
  const result = spawnSync("python3", [
    path.join(root, "scripts", "audit_broll_backgrounds.py"),
    "--registry", path.join(root, "assets", "broll", "template-registry.json"),
    "--tokens", path.join(root, "assets", "presets", "brand-tokens.json"),
  ], {encoding: "utf8", cwd: root});

  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
  const report = JSON.parse(result.stdout);
  assert.equal(report.templateCount, 24);
  assert.equal(report.componentCount, 8);
  assert.equal(report.failedCount, 0);
  assert.equal(report.passedCount, 32);
});

test("shared B-roll components use the same locked background when opened independently", () => {
  const components = path.join(root, "assets", "broll", "library", "components");
  for (const name of fs.readdirSync(components).filter((file) => file.endsWith(".html"))) {
    const source = fs.readFileSync(path.join(components, name), "utf8");
    assert.match(source, /data-broll-background="locked-grid-v1"/, `${name} is not locked`);
    assert.match(source, /data-broll-theme="locked-grid-v1"/, `${name} lacks the canonical theme`);
  }
});

test("the locked B-roll theme is the final style block in every source file", () => {
  const files = [
    ...fs.readdirSync(path.join(root, "assets/broll/fixed")).filter((file) => file.endsWith(".html")).map((file) => path.join(root, "assets/broll/fixed", file)),
    ...fs.readdirSync(path.join(root, "assets/broll/library/templates")).filter((file) => file.endsWith(".html")).map((file) => path.join(root, "assets/broll/library/templates", file)),
    ...fs.readdirSync(path.join(root, "assets/broll/library/components")).filter((file) => file.endsWith(".html")).map((file) => path.join(root, "assets/broll/library/components", file)),
  ];
  for (const file of files) {
    const source = fs.readFileSync(file, "utf8");
    const starts = [...source.matchAll(/<style(?:\s[^>]*)?>/g)].map((match) => match.index);
    assert.equal(source.lastIndexOf('<style data-broll-theme="locked-grid-v1">'), starts.at(-1), `${path.basename(file)} allows later CSS to override the background`);
  }
});

test("B-roll background normalization is idempotent", () => {
  const result = spawnSync("python3", [
    path.join(root, "scripts", "normalize_broll_backgrounds.py"),
    "--root", path.join(root, "assets", "broll"),
  ], {encoding: "utf8", cwd: root});
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /0\/32/);
});

test("background review builder exposes every template and component", () => {
  const dir = fs.mkdtempSync(path.join(process.cwd(), ".broll-review-test-"));
  const output = path.join(dir, "index.html");
  const result = spawnSync("python3", [
    path.join(root, "scripts", "build_broll_background_review.py"),
    "--root", path.join(root, "assets", "broll"),
    "--registry", path.join(root, "assets", "broll", "template-registry.json"),
    "--output", output,
  ], {encoding: "utf8", cwd: root});
  try {
    assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
    const html = fs.readFileSync(output, "utf8");
    assert.equal((html.match(/class="preview-card"/g) || []).length, 32);
    assert.match(html, /fixed-chapter-v1/);
    assert.match(html, /t21-chapter-recap/);
    assert.match(html, /cat-cue/);
    const firstPreview = fs.readFileSync(path.join(dir, "pages", "01-fixed-chapter-v1.html"), "utf8");
    assert.match(firstPreview, /innerWidth\s*\/\s*1920/);
    assert.match(firstPreview, /width:1920px!important;height:1080px!important/);
  } finally {
    fs.rmSync(dir, {recursive: true, force: true});
  }
});
