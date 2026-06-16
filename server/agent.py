#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务器本地巡检 Agent

运行于每台被巡检的 Windows/Linux 服务器上，暴露 HTTP 接口供本地客户端查询。
纯标准库实现，零第三方依赖。

Local inspection Agent running on each Windows/Linux server being inspected,
exposing an HTTP interface for the local client to query.
Implemented with the pure standard library and zero third-party dependencies.

运行方式 / Usage:
    python agent.py [--port 5000]

服务扩展 / Extending services:
    如需新增巡检项（如 IIS、SQL Server、CPU、内存等），
    请在 services/ 目录下新建文件并实现 collect() 函数，
    然后在下方的 get_health_data() 中引用。

    To add new inspection items (e.g. IIS, SQL Server, CPU, memory),
    create a new file under services/ and implement a collect() function,
    then reference it in get_health_data() below.

Windows 后台运行建议 / Suggestions for running on Windows in the background:
    - 使用 nssm 封装为 Windows Service
      Use nssm to wrap it as a Windows Service
    - 或添加为计划任务（启动时运行）
      Or add it as a scheduled task (run at startup)
    - 或 PowerShell: Start-Process python -ArgumentList "agent.py" -WindowStyle Hidden
      Or PowerShell: Start-Process python -ArgumentList "agent.py" -WindowStyle Hidden
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

# 如需启用 IIS 检查，取消下一行注释 / To enable IIS checking, uncomment the next line
# from services.iis import collect as collect_iis


# 默认输出语言 / Default output language
DEFAULT_LANG = "zh"

# 当前运行语言，由命令行参数设置 / Current runtime language, set by command-line argument
_CURRENT_LANG = DEFAULT_LANG

# 翻译表 / Translation table
TRANSLATIONS = {
    "zh": {
        "argparse_description": "服务器巡检 Agent",
        "port_help": "监听端口 (默认: 5000)",
        "lang_help": "输出语言 (默认: zh)",
        "collect_service_failed": "采集服务 {name} 失败: {error}",
        "health_request_error": "处理 /health 请求时发生错误: {error}",
        "agent_started": "Agent 已启动，监听 {url}",
        "press_ctrl_c_to_stop": "按 Ctrl+C 停止",
        "agent_stopping": "Agent 正在停止...",
        "agent_stopped": "Agent 已停止",
        "not_found": "未找到",
    },
    "en": {
        "argparse_description": "Server inspection Agent",
        "port_help": "Listen port (default: 5000)",
        "lang_help": "Output language (default: zh)",
        "collect_service_failed": "Collector {name} failed: {error}",
        "health_request_error": "Error handling /health request: {error}",
        "agent_started": "Agent started, listening on {url}",
        "press_ctrl_c_to_stop": "Press Ctrl+C to stop",
        "agent_stopping": "Agent is stopping...",
        "agent_stopped": "Agent stopped",
        "not_found": "not found",
    },
}


def t(key: str, lang: str = None, **kwargs) -> str:
    """获取指定语言的翻译文本 / Get translated text for the specified language."""
    if lang is None:
        lang = _CURRENT_LANG
    text = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANG]).get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text


# 配置日志：时间 级别 消息 / Configure logging: timestamp level message
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _safe_collect(name, collector, lang=None):
    """安全执行采集函数，单个服务异常不影响整体返回。

    Safely execute a collector so a single service failure does not affect the overall response.
    """
    if lang is None:
        lang = _CURRENT_LANG
    try:
        return collector(lang=lang)
    except Exception as e:
        logger.warning(t("collect_service_failed", name=name, error=e))
        return {"error": str(e), "traceback": traceback.format_exc()}


def get_health_data(lang=None):
    """组装健康检查数据。

    Assemble health-check data.
    """
    if lang is None:
        lang = _CURRENT_LANG
    data = {
        "status": "running",
        "os": platform.system(),
        "disks": _safe_collect("disk", collect_disk, lang=lang),
        "cpu": _safe_collect("cpu", collect_cpu, lang=lang),
        "memory": _safe_collect("memory", collect_memory, lang=lang),
    }

    # 扩展点：新增服务在此加入返回数据 / Extension point: add new services to the returned data here
    # try:
    #     data["iis"] = _safe_collect("iis", collect_iis)
    # except Exception as e:
    #     data["iis"] = {"error": str(e)}

    return data


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器。

    HTTP request handler.
    """

    def log_message(self, format, *args):
        # 使用标准日志库输出访问日志，包含客户端 IP / Use the standard logging library to output access logs, including client IP
        logger.info(f"{self.client_address[0]} - {args[0]}")

    def _send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _send_error(self, code, message):
        """统一的错误响应格式。

        Unified error response format.
        """
        self._send_json(code, {"status": "error", "message": message})

    def do_GET(self):
        if self.path == "/health":
            try:
                data = get_health_data()
                self._send_json(200, data)
            except Exception as e:
                logger.error(t("health_request_error", error=e))
                self._send_error(500, str(e))
        elif self.path == "/ping":
            # 轻量级存活探测，不执行任何采集 / Lightweight liveness probe; does not perform any collection
            self._send_json(200, {"status": "ok"})
        else:
            self._send_error(404, "not_found")


def run_server(port):
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(t("agent_started", url=f"http://0.0.0.0:{port}/health"))
    logger.info(t("press_ctrl_c_to_stop"))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info(t("agent_stopping"))
        server.shutdown()
        logger.info(t("agent_stopped"))


def parse_args():
    """解析命令行参数。

    Parse command-line arguments.
    """
    # 先解析 --lang，使 argparse 帮助信息使用正确语言 / Parse --lang first so argparse help text uses the correct language
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument(
        "--lang",
        type=str,
        default=DEFAULT_LANG,
        choices=["zh", "en"],
    )
    pre_args, _ = pre_parser.parse_known_args()
    global _CURRENT_LANG
    _CURRENT_LANG = pre_args.lang

    parser = argparse.ArgumentParser(description=t("argparse_description"))
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help=t("port_help"),
    )
    parser.add_argument(
        "--lang",
        type=str,
        default=DEFAULT_LANG,
        choices=["zh", "en"],
        help=t("lang_help"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    _CURRENT_LANG = args.lang
    run_server(args.port)
