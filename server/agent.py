#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务器本地巡检 Agent

运行于每台被巡检的 Windows/Linux 服务器上，暴露 HTTP 接口供本地客户端查询。
纯标准库实现，零第三方依赖。

运行方式:
    python agent.py [--port 5000]

服务扩展:
    如需新增巡检项（如 IIS、SQL Server、CPU、内存等），
    请在 services/ 目录下新建文件并实现 collect() 函数，
    然后在下方的 get_health_data() 中引用。

Windows 后台运行建议:
    - 使用 nssm 封装为 Windows Service
    - 或添加为计划任务（启动时运行）
    - 或 PowerShell: Start-Process python -ArgumentList "agent.py" -WindowStyle Hidden
"""

import argparse
import platform
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

from services.disk import collect as collect_disk

# 如需启用 IIS 检查，取消下一行注释
# from services.iis import collect as collect_iis


def get_health_data():
    """组装健康检查数据"""
    data = {
        "status": "running",
        "os": platform.system(),
        "disks": collect_disk(),
    }

    # 扩展点：新增服务在此加入返回数据
    # try:
    #     data["iis"] = collect_iis()
    # except Exception as e:
    #     data["iis"] = {"error": str(e)}

    return data


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    def log_message(self, format, *args):
        # 覆写为简单日志，可注释掉以下行以完全静默
        print(f"[{self.log_date_time_string()}] {args[0]}")

    def do_GET(self):
        if self.path == "/health":
            try:
                data = get_health_data()
                self._send_json(200, data)
            except Exception as e:
                self._send_json(500, {"status": "error", "message": str(e)})
        else:
            self._send_json(404, {"status": "not_found"})

    def _send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())


def run_server(port):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"Agent 已启动，监听 http://0.0.0.0:{port}/health")
    print("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAgent 正在停止...")
        server.shutdown()
        print("Agent 已停止")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="服务器巡检 Agent")
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="监听端口 (默认: 5000)",
    )
    args = parser.parse_args()
    run_server(args.port)
