process.env.IP_COURSE_HOME = process.env.IP_COURSE_TEST_HOME || "/nonexistent/ip-course-test-home";
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {spawnSync} from "node:child_process";
import {prepareReviewArtifacts, skillRoot} from "./helpers/workflow-fixture.mjs";

const run = (script, args) => spawnSync(
  "python3",
  [path.join(skillRoot, "scripts", script), ...args],
  {encoding: "utf8"},
);

test("environment review foregrounds the concrete A-roll location and hides full narration", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ip-course-environment-review-"));
  const project = path.join(dir, "project");
  assert.equal(run("init_project.py", ["--root", project, "--project-id", "review", "--chapters", "01"]).status, 0);
  prepareReviewArtifacts(project);

  const planPath = path.join(project, "planning/environment-cast-plan.json");
  const plan = JSON.parse(fs.readFileSync(planPath, "utf8"));
  plan.chapters[0].background = {
    ...plan.chapters[0].background,
    label: "现代开放式科技办公室",
    locationType: "办公室",
    timeAndLighting: "白天；落地窗自然光与暖色吊灯",
    spatialLayout: "左侧办公桌，中间任务轨道，右侧文件交付柜",
    keyProps: ["木质办公桌", "超宽显示器", "文件交付柜"],
  };
  fs.writeFileSync(planPath, JSON.stringify(plan, null, 2));

  const output = path.join(project, "reviews/environment-cast-review.html");
  const result = run("build_environment_cast_review.py", ["--project-root", project, "--output", output]);
  assert.equal(result.status, 0, result.stderr);

  const html = fs.readFileSync(output, "utf8");
  assert.match(html, /现代开放式科技办公室/);
  assert.match(html, /具体场所.*办公室/s);
  assert.match(html, /光线.*落地窗自然光与暖色吊灯/s);
  assert.match(html, /空间布局.*左侧办公桌，中间任务轨道，右侧文件交付柜/s);
  assert.match(html, /关键道具.*木质办公桌.*超宽显示器.*文件交付柜/s);
  assert.doesNotMatch(html, /真实口播/);
  assert.doesNotMatch(html, /开始讲解/);
});
