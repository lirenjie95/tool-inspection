#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内存信息采集服务

Memory information collection service.
"""

import json
import platform
import subprocess


def collect():
    """
    采集内存使用情况。

    Collect memory usage.

    Returns:
        dict: 包含 total_mb, free_mb, used_percent
        dict: Contains total_mb, free_mb, used_percent.
    """
    os_type = platform.system()
    if os_type == "Windows":
        return _collect_windows()
    else:
        return _collect_linux()


def _collect_windows():
    """Windows: 通过 PowerShell 获取内存信息。

    Windows: get memory information via PowerShell.
    """
    ps_cmd = (
        "Get-WmiObject Win32_OperatingSystem | "
        "Select-Object TotalVisibleMemorySize, FreePhysicalMemory | "
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
    total_kb = data.get("TotalVisibleMemorySize", 0)
    free_kb = data.get("FreePhysicalMemory", 0)

    total_mb = round(total_kb / 1024, 0)
    free_mb = round(free_kb / 1024, 0)
    used_percent = round((total_kb - free_kb) / total_kb * 100, 1) if total_kb else 0

    return {
        "total_mb": int(total_mb),
        "free_mb": int(free_mb),
        "used_percent": used_percent,
    }


def _collect_linux():
    """Linux: 通过 free 命令获取内存信息。

    Linux: get memory information via the free command.
    """
    try:
        output = subprocess.check_output(
            ["free", "-m"],
            text=True,
        ).strip().splitlines()
        # 第二行是内存信息
        # The second line is memory information
        if len(output) < 2:
            return {"total_mb": 0, "free_mb": 0, "used_percent": 0}

        parts = output[1].split()
        # 格式: total used free shared buff/cache available
        # Format: total used free shared buff/cache available
        if len(parts) < 4:
            return {"total_mb": 0, "free_mb": 0, "used_percent": 0}

        total_mb = int(parts[1])
        free_mb = int(parts[3])
        used_percent = round((total_mb - free_mb) / total_mb * 100, 1) if total_mb else 0

        return {
            "total_mb": total_mb,
            "free_mb": free_mb,
            "used_percent": used_percent,
        }
    except Exception:
        return {"total_mb": 0, "free_mb": 0, "used_percent": 0}
