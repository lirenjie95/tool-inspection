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
import json
import logging
import platform
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler

from services.disk import collect as collect_disk
from services.cpu import collect as collect_cpu
from services.memory import collect as collect_memory

# 如需启用 IIS 检查，取消下一行注释
# from services.iis import collect as collect_iis


# 配置日志：时间 级别 消息
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _safe_collect(name, collector):
    """安全执行采集函数，单个服务异常不影响整体返回"""
    try:
        return collector()
    except Exception as e:
        logger.warning(f"采集服务 {name} 失败: {e}")
        return {"error": str(e), "traceback": traceback.format_exc()}


def get_health_data():
    """组装健康检查数据"""
    data = {
        "status": "running",
        "os": platform.system(),
        "disks": _safe_collect("disk", collect_disk),
        "cpu": _safe_collect("cpu", collect_cpu),
        "memory": _safe_collect("memory", collect_memory),
    }

    # 扩展点：新增服务在此加入返回数据
    # try:
    #     data["iis"] = _safe_collect("iis", collect_iis)
    # except Exception as e:
    #     data["iis"] = {"error": str(e)}

    return data


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    def log_message(self, format, *args):
        # 使用标准日志库输出访问日志，包含客户端 IP
        logger.info(f"{self.client_address[0]} - {args[0]}")

    def _send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _send_error(self, code, message):
        """统一的错误响应格式"""
        self._send_json(code, {"status": "error", "message": message})

    def do_GET(self):
        if self.path == "/health":
            try:
                data = get_health_data()
                self._send_json(200, data)
            except Exception as e:
                logger.error(f"处理 /health 请求时发生错误: {e}")
                self._send_error(500, str(e))
        elif self.path == "/ping":
            # 轻量级存活探测，不执行任何采集
            self._send_json(200, {"status": "ok"})
        else:
            self._send_error(404, "not_found")


def run_server(port):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"Agent 已启动，监听 http://0.0.0.0:{port}/health")
    logger.info("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Agent 正在停止...")
        server.shutdown()
        logger.info("Agent 已停止")


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
