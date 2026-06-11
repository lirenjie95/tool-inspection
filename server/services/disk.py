#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""磁盘空间信息采集服务"""

import json
import platform
import subprocess


def collect():
    """
    采集磁盘信息。
    
    Returns:
        list[dict]: 磁盘列表，每个元素包含 DeviceID, FreeSpaceGB, SizeGB
    """
    os_type = platform.system()
    if os_type == "Windows":
        return _collect_windows()
    else:
        return _collect_linux()


def _collect_windows():
    """Windows: 通过 PowerShell 获取所有本地磁盘信息"""
    ps_cmd = (
        "Get-WmiObject Win32_LogicalDisk | "
        "Where-Object { $_.DriveType -eq 3 } | "
        "Select-Object DeviceID, "
        "@{n='FreeSpaceGB';e={[math]::Round($_.FreeSpace/1GB,0)}}, "
        "@{n='SizeGB';e={[math]::Round($_.Size/1GB,0)}} | "
        "ConvertTo-Json"
    )
    result = subprocess.run(
        ["powershell", "-Command", ps_cmd],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"PowerShell 执行失败: {result.stderr}")

    data = json.loads(result.stdout)
    # PowerShell 单条记录返回 dict，多条返回 list，统一为 list
    if isinstance(data, dict):
        data = [data]
    return data


def _collect_linux():
    """
    Linux: 使用 df 获取 / 和 /data 挂载点磁盘信息。
    """
    import os
    import subprocess

    mounts = ["/", "/data"]
    result = []

    for mount in mounts:
        # 跳过不存在的挂载点（/ 除外）
        if mount != "/" and not os.path.ismount(mount):
            continue

        try:
            output = subprocess.check_output(
                ["df", "-BG", mount],
                text=True,
            ).strip().splitlines()[-1]
            parts = output.split()
            # 格式: Filesystem 1G-blocks Used Available Use% Mounted on
            if len(parts) >= 6:
                total_gb = int(parts[1].replace("G", ""))
                free_gb = int(parts[3].replace("G", ""))
                result.append({
                    "DeviceID": mount,
                    "FreeSpaceGB": free_gb,
                    "SizeGB": total_gb,
                })
        except Exception:
            continue

    # 如果什么都没采集到，至少返回根分区占位
    if not result:
        result.append({"DeviceID": "/", "FreeSpaceGB": 0, "SizeGB": 0})

    return result
