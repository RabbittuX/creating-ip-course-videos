"""Offline test of scripts/tts_doubao.py against a local mock Doubao server.

Safety: fake credentials, endpoint redirected to 127.0.0.1, and https_proxy pointed
at a dead port so no real HTTPS request can leave this machine.
"""
import base64
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
FAKE_APPID, FAKE_TOKEN = "FAKE_APPID_123", "FAKE_TOKEN_should_never_print"
work = Path(tempfile.mkdtemp(prefix="tts-mock-"))

# a real short mp3 for the mock to return
mp3 = work / "tone.mp3"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1.5",
                "-ar", "24000", "-ac", "1", str(mp3)], check=True)
MP3_B64 = base64.b64encode(mp3.read_bytes()).decode()

requests, mode = [], {"value": "ok"}


class Mock(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        requests.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
        if mode["value"] == "ok":
            resp = {"code": 3000, "message": "Success", "data": MP3_B64}
        elif mode["value"] == "bad_voice":
            resp = {"code": 3001, "message": "resource not granted"}
        else:  # "crash"
            self.send_response(500); self.end_headers(); return
        data = json.dumps(resp).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(data)


server = http.server.HTTPServer(("127.0.0.1", 0), Mock)
threading.Thread(target=server.serve_forever, daemon=True).start()
ENDPOINT = f"http://127.0.0.1:{server.server_port}/api/v1/tts"

home = work / "home"
home.mkdir()
cfg = json.loads((SKILL / "config.example.json").read_text())
cfg["tts"].update({"voiceType": "mock_voice_for_test", "ratePercent": 8})
(home / "config.json").write_text(json.dumps(cfg, ensure_ascii=False))

chapter_text = "第一章开场。这是一整章的口播，" + "包含很多句子。" * 30 + "最后一句结束。"
manifest = work / "narration-manifest.json"
manifest.write_text(json.dumps({"chapters": [
    {"chapterId": "01", "narration": chapter_text},
    {"chapterId": "02", "narration": "第二章。"}]}, ensure_ascii=False))

RUNNER = (
    "import sys,runpy;sys.path.insert(0,sys.argv[1]);import tts_doubao as t;"
    "t.ENDPOINT=sys.argv[2];sys.argv=[t.__file__]+sys.argv[3:];raise SystemExit(t.main())"
)


def run(args, creds=True, proxy=True):
    env = dict(os.environ, IP_COURSE_HOME=str(home))
    env.pop("DOUBAO_APPID", None); env.pop("DOUBAO_TOKEN", None)  # drop the REAL keys
    if creds:
        env.update(DOUBAO_APPID=FAKE_APPID, DOUBAO_TOKEN=FAKE_TOKEN)
    if proxy:
        env.update(https_proxy="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9", no_proxy="127.0.0.1", NO_PROXY="127.0.0.1")
    return subprocess.run([sys.executable, "-c", RUNNER, str(SKILL / "scripts"), ENDPOINT, *args],
                          capture_output=True, text=True, env=env)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,sample_rate,channels",
                          "-show_entries", "format=duration", "-of", "json", str(path)], capture_output=True, text=True).stdout
    return json.loads(out)


results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("✅" if cond else "❌"), name, ("— " + detail if detail and not cond else ""))


# 1. happy path: whole chapter, one request, wav output
requests.clear()
out = work / "audio" / "01.wav"
r = run(["--narration-manifest", str(manifest), "--chapter", "01", "--output", str(out)])
check("整章合成成功退出码 0", r.returncode == 0, r.stderr)
check("整章只发了 1 次请求（不拆句）", len(requests) == 1, str(len(requests)))
b = requests[0]["body"] if requests else {}
check("请求里是完整整章文本", b.get("request", {}).get("text") == chapter_text)
check("只取了指定章节 01，没混入 02", "第二章" not in b.get("request", {}).get("text", ""))
check("音色来自用户配置", b.get("audio", {}).get("voice_type") == "mock_voice_for_test")
check("语速 +8% 换算成 speed_ratio 1.08", b.get("audio", {}).get("speed_ratio") == 1.08, str(b.get("audio")))
check("鉴权头格式 Bearer;<token>", requests and requests[0]["auth"] == "Bearer;" + FAKE_TOKEN)
check("appid/cluster/operation 字段正确", b.get("app", {}).get("appid") == FAKE_APPID and b.get("app", {}).get("cluster") == "volcano_tts" and b.get("request", {}).get("operation") == "query")
check("用的是假密钥，不是你的真实密钥", b.get("app", {}).get("token") == FAKE_TOKEN)
info = probe(out) if out.exists() else {}
st = (info.get("streams") or [{}])[0]
check("输出 wav 为 44.1kHz 双声道", st.get("sample_rate") == "44100" and st.get("channels") == 2, str(st))
check("输出时长与返回音频一致(~1.5s)", abs(float(info.get("format", {}).get("duration", 0)) - 1.5) < 0.1)
check("stdout/stderr 不含 token", FAKE_TOKEN not in r.stdout + r.stderr)

# 2. mp3 output keeps raw bytes
requests.clear()
out_mp3 = work / "audio" / "01.mp3"

(work / "t.txt").write_text("短文本测试。")
r = run(["--text-file", str(work / "t.txt"), "--output", str(out_mp3)])
check("输出 .mp3 时直接写入返回音频", r.returncode == 0 and out_mp3.read_bytes() == mp3.read_bytes(), r.stderr)

# 3. dry-run sends nothing
requests.clear()
r = run(["--text-file", str(work / "t.txt"), "--output", str(work / "x.wav"), "--dry-run"])
check("--dry-run 不发任何请求", r.returncode == 0 and len(requests) == 0)
check("--dry-run 输出里是占位符而非密钥", "<DOUBAO_TOKEN>" in r.stdout and FAKE_TOKEN not in r.stdout)

# 4. missing credentials
requests.clear()
r = run(["--text-file", str(work / "t.txt"), "--output", str(work / "y.wav")], creds=False)
check("缺密钥时拒绝运行且不发请求", r.returncode == 2 and len(requests) == 0 and "DOUBAO_APPID" in r.stderr)

# 5. API error
mode["value"] = "bad_voice"
r = run(["--text-file", str(work / "t.txt"), "--output", str(work / "z.wav")])
check("豆包返回错误码时退出码 1 并报出原因", r.returncode == 1 and "3001" in r.stderr and not (work / "z.wav").exists(), r.stderr)
check("报错信息不含 token", FAKE_TOKEN not in r.stderr)

# 6. server/network failure
mode["value"] = "crash"
r = run(["--text-file", str(work / "t.txt"), "--output", str(work / "w.wav")])
check("服务端 500 时退出码 1、不泄露请求体", r.returncode == 1 and FAKE_TOKEN not in r.stderr and "第" not in r.stderr, r.stderr)

# 7. unknown chapter
mode["value"] = "ok"
requests.clear()
r = run(["--narration-manifest", str(manifest), "--chapter", "99", "--output", str(work / "v.wav")])
check("章节不存在时报错且不发请求", r.returncode != 0 and len(requests) == 0)

# 8. safety net: real endpoint is unreachable through the dead proxy
probe_code = ("import urllib.request,sys\n"
              "try:\n urllib.request.urlopen('https://openspeech.bytedance.com/api/v1/tts', timeout=5); print('REACHED')\n"
              "except Exception as e: print('BLOCKED', type(e).__name__)")
env = dict(os.environ, https_proxy="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9")
env.pop("DOUBAO_TOKEN", None)
p = subprocess.run([sys.executable, "-c", probe_code], capture_output=True, text=True, env=env)
check("保护网生效：测试环境下连不上真实豆包地址", p.stdout.startswith("BLOCKED"), p.stdout)

server.shutdown()
print(f"\n共 {len(results)} 项，通过 {sum(ok for _, ok in results)} 项；模拟服务器共收到请求都来自 127.0.0.1")
sys.exit(0 if all(ok for _, ok in results) else 1)
