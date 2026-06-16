#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CPU 使用率信息采集服务

CPU usage information collection service.
"""

import json
import platform
import subprocess


def collect():
    """
    采集 CPU 使用率。

    Collect CPU usage.

    Returns:
        dict: 包含 usage_percent（总体使用率）
        dict: Contains usage_percent (overall usage).
    """
    os_type = platform.system()
    if os_type == "Windows":
        return _collect_windows()
    else:
        return _collect_linux()


def _collect_windows():
    """Windows: 通过 PowerShell 获取 CPU 平均使用率。

    Windows: get average CPU usage via PowerShell.
    """
    ps_cmd = (
        "$cpus = Get-WmiObject Win32_Processor | Select-Object LoadPercentage; "
        "$cpus | Select-Object -ExpandProperty LoadPercentage | ConvertTo-Json"
    )
    result = subprocess.run(
        ["powershell", "-Command", ps_cmd],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"PowerShell 执行失败: {result.stderr}")

    data = json.loads(result.stdout)
    if isinstance(data, int):
        values = [data]
    elif isinstance(data, float):
        values = [data]
    elif isinstance(data, list):
        values = [v for v in data if isinstance(v, (int, float))]
    else:
        values = []

    if not values:
        return {"usage_percent": 0}

    avg = round(sum(values) / len(values), 1)
    return {"usage_percent": avg}


def _collect_linux():
    """Linux: 通过 /proc/stat 计算 CPU 使用率。

    Linux: calculate CPU usage via /proc/stat.
    """
    try:
        with open("/proc/stat", "r") as f:
            line1 = f.readline().strip()
        if not line1.startswith("cpu "):
            return {"usage_percent": 0}

        fields1 = [int(x) for x in line1.split()[1:]]
        total1 = sum(fields1)
        idle1 = fields1[3]

        import time
        time.sleep(0.1)

        with open("/proc/stat", "r") as f:
            line2 = f.readline().strip()
        fields2 = [int(x) for x in line2.split()[1:]]
        total2 = sum(fields2)
        idle2 = fields2[3]

        total_diff = total2 - total1
        idle_diff = idle2 - idle1
        if total_diff <= 0:
            return {"usage_percent": 0}

        usage = round((1 - idle_diff / total_diff) * 100, 1)
        return {"usage_percent": usage}
    except Exception:
        return {"usage_percent": 0}
