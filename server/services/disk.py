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
    Linux: 使用 df 获取所有真实挂载点磁盘信息。
    自动过滤伪文件系统（如 devtmpfs、tmpfs、overlay 等）。
    """
    import os
    import subprocess

    # 需要忽略的伪文件系统类型
    skip_fs_types = {"devtmpfs", "tmpfs", "overlay", "squashfs", "proc", "sysfs", "cgroup"}
    result = []

    try:
        output = subprocess.check_output(
            ["df", "-BG"],
            text=True,
        ).strip().splitlines()
    except Exception:
        output = []

    # 第一行是表头，跳过
    for line in output[1:]:
        parts = line.split()
        # 格式: Filesystem 1G-blocks Used Available Use% Mounted on
        if len(parts) < 6:
            continue

        fs_type_or_device = parts[0]
        mount_point = " ".join(parts[5:]) if len(parts) > 6 else parts[5]

        # 跳过伪文件系统和特殊挂载点
        if fs_type_or_device in skip_fs_types:
            continue
        if mount_point.startswith("/dev") or mount_point.startswith("/sys") or mount_point.startswith("/proc"):
            continue
        if not os.path.ismount(mount_point):
            continue

        try:
            total_gb = int(parts[1].replace("G", ""))
            free_gb = int(parts[3].replace("G", ""))
            result.append({
                "DeviceID": mount_point,
                "FreeSpaceGB": free_gb,
                "SizeGB": total_gb,
            })
        except (ValueError, IndexError):
            continue

    # 如果什么都没采集到，至少返回根分区占位
    if not result:
        result.append({"DeviceID": "/", "FreeSpaceGB": 0, "SizeGB": 0})

    return result
