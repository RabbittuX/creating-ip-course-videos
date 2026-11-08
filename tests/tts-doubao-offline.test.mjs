import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import {spawnSync} from "node:child_process";

// Offline only: fake credentials, a local mock server, and a dead HTTPS proxy.
// It never reaches the real Doubao endpoint and never spends quota.
test("Doubao TTS works end to end against a local mock server", () => {
  const env = {...process.env, https_proxy: "http://127.0.0.1:9", HTTPS_PROXY: "http://127.0.0.1:9", no_proxy: "127.0.0.1", NO_PROXY: "127.0.0.1"};
  delete env.DOUBAO_APPID;
  delete env.DOUBAO_TOKEN;
  const result = spawnSync("python3", [path.join(import.meta.dirname, "tts_doubao_offline.py")], {encoding: "utf8", env});
  assert.equal(result.status, 0, result.stdout + result.stderr);
});
