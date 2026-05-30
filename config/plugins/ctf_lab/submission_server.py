"""
CTF Flag 提交服务器
轻量级 HTTP 服务，接收 flag 提交并验证

API:
  POST /submit?flag=XXX     提交 flag
  GET  /status              查看提交记录
  GET  /                    服务信息
"""

import os
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 读取 flag 列表
FLAGS = set()
flags_file = "/shared/flags.txt"
if os.path.exists(flags_file):
    with open(flags_file) as f:
        for line in f:
            flag = line.strip()
            if flag:
                FLAGS.add(flag)

# 也从环境变量读取（备用）
for key in ("FLAG1", "FLAG2", "FLAG3"):
    val = os.environ.get(key, "")
    if val:
        FLAGS.add(val)

# 提交记录
submissions = []


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/status":
            self._json_response({
                "total_flags": len(FLAGS),
                "submissions": submissions,
                "found_count": len([s for s in submissions if s["correct"]]),
            })
        elif parsed.path == "/submit":
            # GET 也支持提交（方便 wget 使用）
            self._handle_submit(parsed)
        else:
            self._json_response({
                "service": "CTF Flag Submission Server",
                "endpoints": {
                    "/submit?flag=XXX": "提交 flag (GET/POST)",
                    "/status": "查看提交记录",
                },
            })

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/submit":
            self._handle_submit(parsed)
        else:
            self._json_response({"error": "Not found"}, 404)

    def _handle_submit(self, parsed):
        params = parse_qs(parsed.query)
        flag = params.get("flag", [""])[0]

        if not flag:
            self._json_response({"success": False, "message": "缺少 flag 参数，用法: /submit?flag=YOUR_FLAG"}, 400)
            return

        correct = flag in FLAGS
        already = any(s["flag"] == flag and s["correct"] for s in submissions)

        record = {
            "flag": flag,
            "correct": correct,
            "already_found": already,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        submissions.append(record)

        if already:
            self._json_response({"success": True, "message": "Flag 已提交过", "correct": True})
        elif correct:
            self._json_response({"success": True, "message": "Flag 正确!", "correct": True})
        else:
            self._json_response({"success": True, "message": "Flag 错误", "correct": False})

    def _json_response(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # 静默日志


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Submission server running on port {port}")
    print(f"Loaded {len(FLAGS)} flags")
    server.serve_forever()
