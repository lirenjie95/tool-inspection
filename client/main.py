#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地巡检客户端

向各服务器的 Agent 发起 HTTP 查询，汇总输出巡检结果。

运行方式:
    python main.py
    python main.py --output report.txt
    python main.py --output report.json
    python main.py --config config_prod.py

依赖:
    pip install requests
"""

import argparse
import importlib.util
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from config import SERVERS, WEBS, DISK_THRESHOLD_GB, ROLE_DISK_THRESHOLDS_GB


def load_config(path: str = "config.py"):
    """动态加载配置文件，默认为当前目录下的 config.py"""
    abs_path = os.path.abspath(path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"配置文件不存在: {abs_path}")

    spec = importlib.util.spec_from_file_location("inspection_config", abs_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


def check_server_agent(server: dict) -> dict:
    """访问服务器 Agent 获取健康数据"""
    url = f"http://{server['ip']}:{server['port']}/health"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        data["_http_ok"] = True
        return data
    except Exception as e:
        return {"status": "unreachable", "error": str(e), "_http_ok": False}


def format_disk_line(disks: list) -> str:
    """
    按需求格式化磁盘输出:
    C盘剩余：XX GB D盘剩余：XXX GB
    """
    items = []
    for d in disks:
        # Windows: "C:" -> "C盘"  |  Linux: "/" -> "/"
        label = d["DeviceID"].replace(":", "盘")
        items.append(f"{label}剩余：{d['FreeSpaceGB']} GB")
    return " ".join(items)


def format_metrics(data: dict) -> str:
    """格式化 CPU 和内存指标"""
    items = []
    cpu = data.get("cpu", {})
    memory = data.get("memory", {})
    if cpu.get("usage_percent") is not None:
        items.append(f"CPU: {cpu['usage_percent']}%")
    if memory.get("used_percent") is not None:
        items.append(f"内存: {memory['used_percent']}%")
    return ", ".join(items) if items else ""


def check_web(url_config: dict) -> dict:
    """检查网页可用性（跟随重定向）"""
    try:
        resp = requests.get(url_config["url"], timeout=20, allow_redirects=True)
        if resp.status_code == 200:
            return {"reachable": True, "status": "正常打开", "code": 200}
        else:
            return {
                "reachable": False,
                "status": f"HTTP {resp.status_code}",
                "code": resp.status_code,
            }
    except Exception as e:
        return {"reachable": False, "status": str(e), "code": None}


def check_all_servers(servers: list) -> list:
    """并发检查所有服务器 Agent，返回 (server, data) 列表"""
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
    # 按原始顺序返回
    order = {id(srv): i for i, srv in enumerate(servers)}
    results.sort(key=lambda x: order[id(x[0])])
    return results


def inspect_server(
    srv: dict,
    data: dict,
    disk_threshold_gb: int = None,
    role_disk_thresholds_gb: dict = None,
) -> tuple:
    """
    检查单台服务器，返回 (lines, warnings)。
    lines 为输出文本行列表，warnings 为异常项列表。
    """
    if disk_threshold_gb is None:
        disk_threshold_gb = DISK_THRESHOLD_GB
    if role_disk_thresholds_gb is None:
        role_disk_thresholds_gb = ROLE_DISK_THRESHOLDS_GB

    lines = []
    warnings = []
    name = srv.get("name", srv["ip"])
    threshold = role_disk_thresholds_gb.get(srv["role"], disk_threshold_gb)

    if data.get("_http_ok") and data.get("status") == "running":
        disks = data.get("disks", [])
        disk_line = format_disk_line(disks)
        lines.append(f"{name} ({srv['ip']}) {disk_line}".strip())
        lines.append(f"  -> 状态: 运行正常")
        metrics = format_metrics(data)
        if metrics:
            lines.append(f"  -> {metrics}")
        min_free = min((d["FreeSpaceGB"] for d in disks), default=0)
        if min_free < threshold:
            lines.append(f"  -> [告警] 磁盘低于阈值 ({threshold}GB)")
            warnings.append(f"{name} ({srv['ip']}): 磁盘空间不足")
        else:
            lines.append(f"  -> 磁盘检查: 通过")
    else:
        lines.append(f"{name} ({srv['ip']}) 状态: {data.get('error', 'Agent 异常')}")
        warnings.append(f"{name} ({srv['ip']}): 不可达")

    return lines, warnings


def run_inspection(
    servers: list = None,
    webs: list = None,
    disk_threshold_gb: int = None,
    role_disk_thresholds_gb: dict = None,
) -> tuple:
    """
    执行完整巡检，返回 (output_text, structured_data)。
    output_text 为供人阅读的多行文本，structured_data 为 JSON 可序列化的字典。
    """
    if servers is None:
        servers = SERVERS
    if webs is None:
        webs = WEBS
    if disk_threshold_gb is None:
        disk_threshold_gb = DISK_THRESHOLD_GB
    if role_disk_thresholds_gb is None:
        role_disk_thresholds_gb = ROLE_DISK_THRESHOLDS_GB

    lines = []
    warnings = []
    structured = {
        "servers": {},
        "webs": [],
        "summary": {"total_warnings": 0, "details": []},
    }

    lines.append("=" * 60)
    lines.append("服务器巡检开始")
    lines.append("=" * 60)

    # ---------- 服务器 ----------
    server_results = check_all_servers(servers)

    # 按角色分组
    by_role: dict = {}
    for srv, data in server_results:
        by_role.setdefault(srv["role"], []).append((srv, data))

    for role in sorted(by_role.keys()):
        servers_in_role = by_role[role]
        role_display = {
            "app": "应用服务器巡检",
            "db": "数据库服务器巡检",
        }.get(role, f"{role} 服务器巡检")
        lines.append(f"\n【{role_display}】")

        for srv, data in servers_in_role:
            srv_lines, srv_warnings = inspect_server(
                srv, data, disk_threshold_gb, role_disk_thresholds_gb
            )
            lines.extend(srv_lines)
            warnings.extend(srv_warnings)
            structured["servers"][srv["ip"]] = {
                "name": srv.get("name", srv["ip"]),
                "role": role,
                "data": data,
                "warnings": srv_warnings,
            }

    # ---------- 网页 ----------
    lines.append("\n【系统网页巡检】")
    for web in webs:
        r = check_web(web)
        lines.append(f"{web['name']} ({web['url']})")
        lines.append(f"  -> 状态: {r['status']} (HTTP {r['code'] or '-' })")
        web_entry = {"name": web["name"], "url": web["url"], **r}
        structured["webs"].append(web_entry)
        if not r["reachable"]:
            warnings.append(f"网页 {web['name']}: {r['status']}")

    # ---------- 汇总 ----------
    lines.append("\n" + "=" * 60)
    lines.append("巡检结果汇总")
    lines.append("=" * 60)
    if not warnings:
        lines.append("所有巡检项均正常")
    else:
        lines.append(f"共发现 {len(warnings)} 项异常，请处理：")
        for w in warnings:
            lines.append(f"   - {w}")
    lines.append("=" * 60)

    structured["summary"]["total_warnings"] = len(warnings)
    structured["summary"]["details"] = warnings

    return "\n".join(lines), structured


def main(argv=None):
    parser = argparse.ArgumentParser(description="服务器巡检客户端")
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default="config.py",
        help="指定配置文件路径 (默认: config.py)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="输出巡检报告到文件（.json 结尾则输出 JSON，否则输出文本）",
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    output_text, structured = run_inspection(
        servers=config.SERVERS,
        webs=config.WEBS,
        disk_threshold_gb=config.DISK_THRESHOLD_GB,
        role_disk_thresholds_gb=getattr(config, "ROLE_DISK_THRESHOLDS_GB", {}),
    )
    print(output_text)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                if args.output.lower().endswith(".json"):
                    json.dump(structured, f, ensure_ascii=False, indent=2)
                else:
                    f.write(output_text)
            print(f"\n[信息] 巡检报告已保存到: {args.output}")
        except Exception as e:
            print(f"\n[错误] 保存报告失败: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
