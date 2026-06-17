#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地巡检客户端 / Local inspection client

向各服务器的 Agent 发起 HTTP 查询，汇总输出巡检结果。
Sends HTTP queries to each server's Agent and aggregates the inspection results.

运行方式 / Usage:
    python main.py
    python main.py --output report.txt
    python main.py --output report.json
    python main.py --config config_prod.json
    python main.py --lang en

依赖 / Dependencies:
    pip install requests
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# 默认输出语言 / Default output language
DEFAULT_LANG = "zh"

# 翻译表 / Translation table
TRANSLATIONS = {
    "zh": {
        "server_inspection_start": "服务器巡检开始",
        "server_inspection_summary": "巡检结果汇总",
        "all_normal": "所有巡检项均正常",
        "issues_found": "共发现 {count} 项异常，请处理：",
        "status_normal": "运行正常",
        "disk_check_passed": "总磁盘空间检查: 通过",
        "disk_warning": "[告警] 总磁盘空间低于阈值 ({threshold}GB)",
        "disk_warning_detail": "{name} ({ip}): 总磁盘空间不足",
        "unreachable_detail": "{name} ({ip}): 不可达",
        "web_warning": "网页 {name}: {status}",
        "agent_error": "Agent 异常",
        "web_status_ok": "正常打开",
        "web_status_prefix": "状态",
        "cpu_prefix": "CPU",
        "memory_prefix": "内存",
        "disk_free_prefix": "剩余",
        "server_inspection_suffix": "服务器巡检",
        "web_inspection": "系统网页巡检",
        "report_saved": "[信息] 巡检报告已保存到: {path}",
        "report_save_failed": "[错误] 保存报告失败: {error}",
        "app_role": "应用服务器巡检",
        "db_role": "数据库服务器巡检",
        "disk_collect_failed": "磁盘采集失败: {error}",
    },
    "en": {
        "server_inspection_start": "Server Inspection Started",
        "server_inspection_summary": "Inspection Summary",
        "all_normal": "All inspection items are normal",
        "issues_found": "{count} issue(s) found, please handle:",
        "status_normal": "OK",
        "disk_check_passed": "Total disk space check: PASSED",
        "disk_warning": "[WARNING] Total disk space below threshold ({threshold}GB)",
        "disk_warning_detail": "{name} ({ip}): insufficient total disk space",
        "unreachable_detail": "{name} ({ip}): unreachable",
        "web_warning": "Web {name}: {status}",
        "agent_error": "Agent error",
        "web_status_ok": "OK",
        "web_status_prefix": "Status",
        "cpu_prefix": "CPU",
        "memory_prefix": "Memory",
        "disk_free_prefix": "free",
        "server_inspection_suffix": "Server Inspection",
        "web_inspection": "Web Page Inspection",
        "report_saved": "[INFO] Inspection report saved to: {path}",
        "report_save_failed": "[ERROR] Failed to save report: {error}",
        "app_role": "App Server Inspection",
        "db_role": "DB Server Inspection",
        "disk_collect_failed": "Disk collection failed: {error}",
    },
}


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """获取指定语言的翻译文本 / Get translated text for the specified language."""
    text = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANG]).get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text


class _JsonConfig:
    """将 JSON 配置包装为与 Python 模块配置相同的属性访问接口
    / Wrap JSON config to provide the same attribute access interface as a Python module config."""

    def __init__(self, data: dict):
        self._data = data

    def __getattr__(self, name: str):
        if name in self._data:
            return self._data[name]
        # 兼容未配置的角色阈值 / Compatibility: return empty dict if role thresholds are not configured
        if name == "ROLE_DISK_THRESHOLDS_GB":
            return {}
        raise AttributeError(f"配置缺少必需项: {name}")


def load_config(path: str = "config.json"):
    """加载 JSON 配置文件，默认为当前目录下的 config.json
    / Load JSON config file; defaults to config.json in the current directory."""
    abs_path = os.path.abspath(path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"配置文件不存在: {abs_path}")

    if not abs_path.lower().endswith(".json"):
        raise ValueError(f"配置文件必须是 JSON 格式: {abs_path}")

    with open(abs_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return _JsonConfig(data)


def _load_default_config():
    """加载默认配置文件（用于 run_inspection 无参调用时）
    / Load the default config file (used when run_inspection is called without arguments)."""
    return load_config(os.path.join(os.path.dirname(__file__), "config.json"))


def check_server_agent(server: dict) -> dict:
    """访问服务器 Agent 获取健康数据 / Query the server Agent for health data."""
    url = f"http://{server['ip']}:{server['port']}/health"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        data["_http_ok"] = True
        return data
    except Exception as e:
        return {"status": "unreachable", "error": str(e), "_http_ok": False}


def format_disk_line(disks: list, lang: str = DEFAULT_LANG) -> str:
    """
    按需求格式化磁盘输出 / Format disk output as required.
    zh: C盘剩余：XX GB D盘剩余：XXX GB
    en: C: XX GB free D: XXX GB free
    """
    items = []
    for d in disks:
        if not isinstance(d, dict):
            continue
        # Windows: "C:" -> "C盘" (zh) / "C:" (en) | Linux: "/" -> "/"
        label = d.get("DeviceID", "")
        if lang == "zh":
            label = label.replace(":", "盘")
        free = d.get("FreeSpaceGB", 0)
        if lang == "zh":
            items.append(f"{label}剩余：{free} GB")
        else:
            items.append(f"{label} {free} GB free")
    return " ".join(items)


def format_metrics(data: dict, lang: str = DEFAULT_LANG) -> str:
    """格式化 CPU 和内存指标 / Format CPU and memory metrics."""
    items = []
    cpu = data.get("cpu", {})
    memory = data.get("memory", {})
    if cpu.get("usage_percent") is not None:
        items.append(f"{t('cpu_prefix', lang)}: {cpu['usage_percent']}%")
    if memory.get("used_percent") is not None:
        items.append(f"{t('memory_prefix', lang)}: {memory['used_percent']}%")
    return ", ".join(items) if items else ""


def check_web(url_config: dict, lang: str = DEFAULT_LANG) -> dict:
    """检查网页可用性（跟随重定向）/ Check web page availability (follows redirects)."""
    try:
        resp = requests.get(url_config["url"], timeout=20, allow_redirects=True)
        if resp.status_code == 200:
            return {"reachable": True, "status": t("web_status_ok", lang), "code": 200}
        else:
            return {
                "reachable": False,
                "status": f"HTTP {resp.status_code}",
                "code": resp.status_code,
            }
    except Exception as e:
        return {"reachable": False, "status": str(e), "code": None}


def check_all_servers(servers: list) -> list:
    """并发检查所有服务器 Agent，返回 (server, data) 列表
    / Concurrently check all server Agents and return a list of (server, data) tuples."""
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_server = {
            executor.submit(check_server_agent, srv): srv for srv in servers
        }
        for future in as_completed(future_to_server):
            srv = future_to_server[future]
            try:
                data = future.result()
            except Exception as e:
                data = {"status": "unreachable", "error": str(e), "_http_ok": False}
            results.append((srv, data))
    # 按原始顺序返回 / Preserve original order
    order = {id(srv): i for i, srv in enumerate(servers)}
    results.sort(key=lambda x: order[id(x[0])])
    return results


def inspect_server(
    srv: dict,
    data: dict,
    disk_threshold_gb: int = None,
    role_disk_thresholds_gb: dict = None,
    lang: str = DEFAULT_LANG,
) -> tuple:
    """
    检查单台服务器，返回 (lines, warnings)。
    Check a single server and return (lines, warnings).
    lines 为输出文本行列表 / lines is a list of output text lines.
    warnings 为异常项列表 / warnings is a list of anomaly items.
    """
    if disk_threshold_gb is None:
        disk_threshold_gb = _load_default_config().DISK_THRESHOLD_GB
    if role_disk_thresholds_gb is None:
        role_disk_thresholds_gb = {}

    lines = []
    warnings = []
    name = srv.get("name", srv["ip"])
    threshold = role_disk_thresholds_gb.get(srv["role"], disk_threshold_gb)

    if data.get("_http_ok") and data.get("status") == "running":
        disks = data.get("disks", [])
        # 磁盘采集失败时返回的是 {"error": ..., "traceback": ...} 字典
        # When disk collection fails, an {"error": ..., "traceback": ...} dict is returned
        if not isinstance(disks, list):
            error = disks.get("error", t("agent_error", lang)) if isinstance(disks, dict) else str(disks)
            lines.append(f"{name} ({srv['ip']}) {t('web_status_prefix', lang)}: {t('disk_collect_failed', lang, error=error)}")
            warnings.append(t("disk_warning_detail", lang, name=name, ip=srv["ip"]))
        else:
            disk_line = format_disk_line(disks, lang=lang)
            lines.append(f"{name} ({srv['ip']}) {disk_line}".strip())
            lines.append(f"  -> {t('web_status_prefix', lang)}: {t('status_normal', lang)}")
            metrics = format_metrics(data, lang=lang)
            if metrics:
                lines.append(f"  -> {metrics}")
            total_free = sum(d.get("FreeSpaceGB", 0) for d in disks if isinstance(d, dict))
            if total_free < threshold:
                lines.append(f"  -> {t('disk_warning', lang, threshold=threshold)}")
                warnings.append(t("disk_warning_detail", lang, name=name, ip=srv["ip"]))
            else:
                lines.append(f"  -> {t('disk_check_passed', lang)}")
    else:
        error = data.get("error", t("agent_error", lang))
        lines.append(f"{name} ({srv['ip']}) {t('web_status_prefix', lang)}: {error}")
        warnings.append(t("unreachable_detail", lang, name=name, ip=srv["ip"]))

    return lines, warnings


def run_inspection(
    servers: list = None,
    webs: list = None,
    disk_threshold_gb: int = None,
    role_disk_thresholds_gb: dict = None,
    lang: str = DEFAULT_LANG,
) -> tuple:
    """
    执行完整巡检，返回 (output_text, structured_data)。
    Run a full inspection and return (output_text, structured_data).
    output_text 为供人阅读的多行文本 / output_text is human-readable multi-line text.
    structured_data 为 JSON 可序列化的字典 / structured_data is a JSON-serializable dictionary.
    """
    if servers is None:
        default_cfg = _load_default_config()
        servers = default_cfg.SERVERS
    if webs is None:
        default_cfg = default_cfg if "default_cfg" in locals() else _load_default_config()
        webs = default_cfg.WEBS
    if disk_threshold_gb is None:
        default_cfg = default_cfg if "default_cfg" in locals() else _load_default_config()
        disk_threshold_gb = default_cfg.DISK_THRESHOLD_GB
    if role_disk_thresholds_gb is None:
        default_cfg = default_cfg if "default_cfg" in locals() else _load_default_config()
        role_disk_thresholds_gb = getattr(default_cfg, "ROLE_DISK_THRESHOLDS_GB", {})

    lines = []
    warnings = []
    structured = {
        "servers": {},
        "webs": [],
        "summary": {"total_warnings": 0, "details": []},
    }

    sep = "=" * 60
    lines.append(sep)
    lines.append(t("server_inspection_start", lang))
    lines.append(sep)

    # ---------- 服务器 / Servers ----------
    server_results = check_all_servers(servers)

    # 按角色分组 / Group by role
    by_role: dict = {}
    for srv, data in server_results:
        by_role.setdefault(srv["role"], []).append((srv, data))

    role_display_map = {
        "app": t("app_role", lang),
        "db": t("db_role", lang),
    }

    for role in sorted(by_role.keys()):
        servers_in_role = by_role[role]
        role_display = role_display_map.get(role, f"{role} {t('server_inspection_suffix', lang)}")
        lines.append(f"\n【{role_display}】")

        for srv, data in servers_in_role:
            srv_lines, srv_warnings = inspect_server(
                srv, data, disk_threshold_gb, role_disk_thresholds_gb, lang=lang
            )
            lines.extend(srv_lines)
            warnings.extend(srv_warnings)
            structured["servers"][srv["ip"]] = {
                "name": srv.get("name", srv["ip"]),
                "role": role,
                "data": data,
                "warnings": srv_warnings,
            }

    # ---------- 网页 / Web pages ----------
    lines.append(f"\n【{t('web_inspection', lang)}】")
    for web in webs:
        r = check_web(web, lang=lang)
        lines.append(f"{web['name']} ({web['url']})")
        lines.append(f"  -> {t('web_status_prefix', lang)}: {r['status']} (HTTP {r['code'] or '-'} )")
        web_entry = {"name": web["name"], "url": web["url"], **r}
        structured["webs"].append(web_entry)
        if not r["reachable"]:
            warnings.append(t("web_warning", lang, name=web["name"], status=r["status"]))

    # ---------- 汇总 / Summary ----------
    lines.append("\n" + sep)
    lines.append(t("server_inspection_summary", lang))
    lines.append(sep)
    if not warnings:
        lines.append(t("all_normal", lang))
    else:
        lines.append(t("issues_found", lang, count=len(warnings)))
        for w in warnings:
            lines.append(f"   - {w}")
    lines.append(sep)

    structured["summary"]["total_warnings"] = len(warnings)
    structured["summary"]["details"] = warnings

    return "\n".join(lines), structured


def main(argv=None):
    parser = argparse.ArgumentParser(description="服务器巡检客户端 / Server inspection client")
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config.json",
        help="指定 JSON 配置文件路径 (默认: config.json) / Path to JSON config file (default: config.json)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="输出巡检报告到文件（.json 结尾则输出 JSON，否则输出文本）/ Save inspection report to file (.json for JSON, otherwise text)",
    )
    parser.add_argument(
        "--lang",
        "-l",
        type=str,
        default=None,
        choices=["zh", "en"],
        help="输出语言 (默认读取配置文件 LANGUAGE，否则为 zh) / Output language (defaults to config LANGUAGE, or zh)",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)

    # 语言优先级：命令行 > 配置文件 > 默认中文
    # Language priority: CLI > config file > default Chinese
    lang = args.lang or getattr(config, "LANGUAGE", DEFAULT_LANG) or DEFAULT_LANG

    output_text, structured = run_inspection(
        servers=config.SERVERS,
        webs=config.WEBS,
        disk_threshold_gb=config.DISK_THRESHOLD_GB,
        role_disk_thresholds_gb=getattr(config, "ROLE_DISK_THRESHOLDS_GB", {}),
        lang=lang,
    )
    print(output_text)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                if args.output.lower().endswith(".json"):
                    json.dump(structured, f, ensure_ascii=False, indent=2)
                else:
                    f.write(output_text)
            print(f"\n{t('report_saved', lang, path=args.output)}")
        except Exception as e:
            print(f"\n{t('report_save_failed', lang, error=e)}", file=sys.stderr)


if __name__ == "__main__":
    main()
