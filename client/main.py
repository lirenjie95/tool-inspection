#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地巡检客户端

向各服务器的 Agent 发起 HTTP 查询，汇总输出巡检结果。

运行方式:
    python main.py

依赖:
    pip install requests
"""

import requests
from config import SERVERS, WEBS, DISK_THRESHOLD_GB


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


def format_disk_line(ip: str, disks: list) -> str:
    """
    按需求格式化磁盘输出:
    IP C盘剩余：XX GB D盘剩余：XXX GB
    """
    items = [ip]
    for d in disks:
        # Windows: "C:" -> "C盘"  |  Linux: "/" -> "/"
        label = d["DeviceID"].replace(":", "盘")
        items.append(f"{label}剩余：{d['FreeSpaceGB']} GB")
    return " ".join(items)


def check_web(url_config: dict) -> dict:
    """检查网页可用性"""
    try:
        resp = requests.get(url_config["url"], timeout=20)
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


def main():
    print("=" * 60)
    print("服务器巡检开始")
    print("=" * 60)

    warnings = []
    results = {"app": [], "db": [], "web": []}

    # 收集服务器数据
    for srv in SERVERS:
        data = check_server_agent(srv)
        results[srv["role"]].append((srv, data))

    # ---------- 应用服务器 ----------
    print("\n【应用服务器巡检】")
    for srv, data in results["app"]:
        if data.get("_http_ok") and data.get("status") == "running":
            print(format_disk_line(srv["ip"], data["disks"]))
            print(f"  -> 状态: 运行正常")
            # 检查阈值
            min_free = (
                min(d["FreeSpaceGB"] for d in data["disks"])
                if data.get("disks")
                else 0
            )
            if min_free < DISK_THRESHOLD_GB:
                msg = f"  -> [告警] 磁盘低于阈值 ({DISK_THRESHOLD_GB}GB)"
                print(msg)
                warnings.append(f"应用服务器 {srv['ip']}: 磁盘空间不足")
            else:
                print(f"  -> 磁盘检查: 通过")
        else:
            print(f"{srv['ip']} 状态: {data.get('error', 'Agent 异常')}")
            warnings.append(f"应用服务器 {srv['ip']}: 不可达")

    # ---------- 数据库服务器 ----------
    print("\n【数据库服务器巡检】")
    for srv, data in results["db"]:
        if data.get("_http_ok") and data.get("status") == "running":
            print(format_disk_line(srv["ip"], data["disks"]))
            print(f"  -> 状态: 运行正常")
            min_free = (
                min(d["FreeSpaceGB"] for d in data["disks"])
                if data.get("disks")
                else 0
            )
            if min_free < DISK_THRESHOLD_GB:
                msg = f"  -> [告警] 磁盘低于阈值 ({DISK_THRESHOLD_GB}GB)"
                print(msg)
                warnings.append(f"数据库服务器 {srv['ip']}: 磁盘空间不足")
            else:
                print(f"  -> 磁盘检查: 通过")
        else:
            print(f"{srv['ip']} 状态: {data.get('error', 'Agent 异常')}")
            warnings.append(f"数据库服务器 {srv['ip']}: 不可达")

    # ---------- 系统网页 ----------
    print("\n【系统网页巡检】")
    for web in WEBS:
        r = check_web(web)
        print(f"{web['name']} ({web['url']})")
        print(f"  -> 状态: {r['status']} (HTTP {r['code'] or '-' })")
        if not r["reachable"]:
            warnings.append(f"网页 {web['name']}: {r['status']}")

    # ---------- 汇总 ----------
    print("\n" + "=" * 60)
    print("巡检结果汇总")
    print("=" * 60)
    if not warnings:
        print("所有巡检项均正常")
    else:
        print(f"共发现 {len(warnings)} 项异常，请处理：")
        for w in warnings:
            print(f"   - {w}")
    print("=" * 60)


if __name__ == "__main__":
    main()
