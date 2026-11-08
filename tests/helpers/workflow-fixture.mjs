import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

export const skillRoot = path.resolve(import.meta.dirname, "../..");
export const sha = (file) => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");

const writeJson = (file, value) => fs.writeFileSync(file, JSON.stringify(value, null, 2));

export function setCanonicalNarration(project, chapterId, narration) {
  const target = path.join(project, "planning/narration-manifest.json");
  const data = JSON.parse(fs.readFileSync(target, "utf8"));
  const byId = new Map(data.chapters.map((item) => [String(item.chapterId), item]));
  byId.set(String(chapterId), {
    chapterId: String(chapterId), narration,
    narrationHash: crypto.createHash("sha256").update(narration).digest("hex"),
  });
  data.chapters = data.chapters.map((item) => byId.get(String(item.chapterId)));
  data.status = data.chapters.every((item) => item.narration) ? "READY" : "DRAFT";
  writeJson(target, data);
}

export function prepareReviewArtifacts(project, chapterId = "01") {
  setCanonicalNarration(project, chapterId, "开始讲解");
  const registryPath = path.join(skillRoot, "assets/character-reference/registry.json");
  const registry = JSON.parse(fs.readFileSync(registryPath, "utf8"));
  const host = registry.characters.find((item) => item.characterId === "ip-host");
  const cast = [{characterId: "ip-host", version: host.version, referenceHash: host.sha256}];
  writeJson(path.join(project, "planning/environment-cast-plan.json"), {
    schemaVersion: 2,
    status: "REVIEW_READY",
    chapters: [{
      chapterId,
      narrationRange: {sourceText: "开始讲解", sourceCharStart: 0, sourceCharEnd: 4},
      background: {backgroundId: "office-v1", label: "办公室", reason: "演示工作流程", sharedWith: []},
      hostPresence: "required",
      cast,
      sceneBible: {environmentDescription: "暖色办公室", screenBackground: "浅色信息屏", cameraFraming: "中景正面", actorPositions: ["IP人物画面左侧", "屏幕画面右侧"], continuityNotes: "保持同一机位与光线"},
      actionChain: ["走向屏幕", "面向屏幕讲解"],
    }],
  });
  writeJson(path.join(project, "planning/visual-outline.json"), {
    schemaVersion: 2,
    status: "REVIEW_READY",
    chapters: [{
      chapterId,
      narration: "开始讲解",
      scenes: [{
        sceneId: `${chapterId}-a1`, type: "A-roll", summary: "IP人物在办公室开始讲解",
        sourceText: "开始讲解", sourceCharStart: 0, sourceCharEnd: 4,
        plannedDurationSeconds: 2, rationale: "建立讲解场景", backgroundId: "office-v1",
        castIds: ["ip-host"], actorAction: "面向屏幕讲解",
      }],
      stats: {totalSeconds: 2, aroll: {seconds: 2, ratio: 1}, broll: {seconds: 0, ratio: 0}},
    }],
    overallStats: {totalSeconds: 2, aroll: {seconds: 2, ratio: 1}, broll: {seconds: 0, ratio: 0}},
  });
  const candidate = path.join(project, "assets/arroll/candidates", `${chapterId}-a1.png`);
  fs.writeFileSync(candidate, "candidate-image");
  writeJson(path.join(project, "planning/aroll-manifest.json"), {
    schemaVersion: 1,
    projectId: "fixture",
    candidateRoot: path.join(project, "assets/arroll/candidates"),
    approvedRoot: path.join(project, "assets/arroll/approved"),
    environmentCastPlan: path.join(project, "planning/environment-cast-plan.json"),
    characterRegistry: registryPath,
    sequences: [{
      id: `${chapterId}-sequence`, chapterId, sceneId: `${chapterId}-a1`, worldLockId: "office-v1", backgroundId: "office-v1",
      castReferences: cast,
      beats: [{
        id: "beat-1", sceneId: `${chapterId}-a1`, role: "establish", candidateId: `${chapterId}-candidate`,
        narrationCue: "开始讲解", actorAction: "面向屏幕讲解", gazeTarget: "screen",
        propState: "screen-on", durationSeconds: 2,
      }],
    }],
    candidates: [{
      candidateId: `${chapterId}-candidate`, assetPath: candidate, assetHash: sha(candidate),
      durationSeconds: 2, sequenceId: `${chapterId}-sequence`, beatId: "beat-1",
      narrationCue: "开始讲解", actorAction: "面向屏幕讲解", gazeTarget: "screen", propState: "screen-on",
    }],
    approvals: {},
  });
}

export function setArtifactStatus(project, file, status) {
  const target = path.join(project, "planning", file);
  const data = JSON.parse(fs.readFileSync(target, "utf8"));
  data.status = status;
  writeJson(target, data);
}

export function writeAudioReady(project, chapterId = "01", narrationText = "开始讲解") {
  const audioDir = path.join(project, "chapters", chapterId, "audio");
  fs.mkdirSync(audioDir, {recursive: true});
  const narration = path.join(audioDir, "narration.txt");
  const audio = path.join(audioDir, "narration.m4a");
  const alignment = path.join(audioDir, "alignment.json");
  fs.writeFileSync(narration, narrationText);
  fs.writeFileSync(audio, "audio-fixture");
  writeJson(alignment, {
    narration: narrationText,
    audioHash: sha(audio),
    tokens: [{id: "t1", text: narrationText, charStart: 0, charEnd: narrationText.length, startMs: 0, endMs: 1000}],
  });
  writeJson(path.join(audioDir, "audio-ready.json"), {
    narrationPath: "narration.txt", audioPath: "narration.m4a", alignmentPath: "alignment.json",
    narrationHash: sha(narration), audioHash: sha(audio), alignmentHash: sha(alignment),
  });
  return {audio, alignment};
}

export function promoteArollFixture(project, chapterId = "01") {
  const manifestPath = path.join(project, "planning/aroll-manifest.json");
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  const candidate = manifest.candidates.find((item) => item.sequenceId === `${chapterId}-sequence`);
  const destination = path.join(project, "assets/arroll/approved", path.basename(candidate.assetPath));
  fs.copyFileSync(candidate.assetPath, destination);
  candidate.status = "APPROVED";
  candidate.approvedAssetPath = destination;
  manifest.approvals[candidate.candidateId] = {assetHash: candidate.assetHash, approvedBy: "fixture", approvedAt: "fixture"};
  writeJson(manifestPath, manifest);
}

export function writeReadyTimeline(project, chapterId = "01") {
  writeJson(path.join(project, "chapters", chapterId, "timing/chapter-timeline.json"), {
    schemaVersion: 1, chapterId, status: "READY", durationMs: 2000,
    titleWindow: {startMs: 0, endMs: 400}, stingWindow: {startMs: 0, endMs: 250},
    narrationWindow: {startMs: 500, endMs: 1800}, captions: [],
  });
}

export function writePreviewReady(project, buildId = "preview-a", chapterId = "01") {
  const previewRoot = path.join(project, "preview");
  fs.mkdirSync(previewRoot, {recursive: true});
  const composition = path.join(previewRoot, "index.html");
  fs.writeFileSync(composition, `<html data-build-id="${buildId}"></html>`);
  const arollComposition = path.join(previewRoot, "fixture-aroll.html");
  fs.writeFileSync(arollComposition, `<main data-aroll-paper style="background:#f8f7f6"><section data-aroll-stage style="left:72px;right:72px;top:70px;height:820px;background:#fdfaf4"><img data-aroll-artwork></section></main>`);
  const visualAssembly = path.join(project, "planning/visual-assembly.json");
  writeJson(visualAssembly, {schemaVersion: 1, status: "READY", fixedAroll: [
    {role: "opening-title", sourcePath: path.join(skillRoot, "assets/arroll/fixed/opening-title.html")},
    {role: "opening-transition", sourcePath: path.join(skillRoot, "assets/arroll/fixed/opening-transition.html")},
  ], arollScenes: [{sceneId: `${chapterId}-a1`, compositionPath: arollComposition}], brollScenes: []});
  const projectFile = path.join(project, "project.json");
  const projectData = JSON.parse(fs.readFileSync(projectFile, "utf8"));
  projectData.visualAssembly = path.relative(project, visualAssembly);
  writeJson(projectFile, projectData);
  const timeline = path.join(project, "timing/full-timeline.json");
  const directives = path.join(project, "planning/creative-directives.json");
  const brollManifest = path.join(project, "planning/broll-manifest.json");
  writeJson(path.join(previewRoot, "preview-ready.json"), {
    schemaVersion: 2, status: "READY", buildId,
    compositionPath: "index.html", compositionHash: sha(composition),
    fullTimelinePath: path.relative(previewRoot, timeline),
    fullTimelineHash: sha(timeline),
    creativeDirectivesPath: path.relative(previewRoot, directives),
    creativeDirectivesHash: sha(directives),
    brollManifestPath: path.relative(previewRoot, brollManifest),
    brollManifestHash: sha(brollManifest),
    visualAssemblyPath: path.relative(previewRoot, visualAssembly),
    visualAssemblyHash: sha(visualAssembly),
  });
}

export function seedGate(stateFile, chapterId, gate, buildId) {
  const data = JSON.parse(fs.readFileSync(stateFile, "utf8"));
  data.chapters[chapterId].requests[gate] = {buildId, requestedAt: "fixture"};
  data.chapters[chapterId].approvals[gate] = {buildId, approvedBy: "fixture", approvedAt: "fixture"};
  writeJson(stateFile, data);
}
