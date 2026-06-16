#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内存信息采集服务

Memory information collection service.
"""

import json
import platform
import subprocess


# 默认输出语言 / Default output language
DEFAULT_LANG = "zh"

# 翻译表 / Translation table
TRANSLATIONS = {
    "zh": {
        "powershell_failed": "PowerShell 执行失败: {error}",
    },
    "en": {
        "powershell_failed": "PowerShell execution failed: {error}",
    },
}


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """获取指定语言的翻译文本 / Get translated text for the specified language."""
    text = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANG]).get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text


def collect(lang: str = DEFAULT_LANG):
    """
    采集内存使用情况。

    Collect memory usage.

    Args:
        lang: 输出语言 (默认 zh) / Output language (default zh).

    Returns:
        dict: 包含 total_mb, free_mb, used_percent
        dict: Contains total_mb, free_mb, used_percent.
    """
    os_type = platform.system()
    if os_type == "Windows":
        return _collect_windows(lang=lang)
    else:
        return _collect_linux(lang=lang)


def _collect_windows(lang: str = DEFAULT_LANG):
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
        raise RuntimeError(t("powershell_failed", lang, error=result.stderr))

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


def _collect_linux(lang: str = DEFAULT_LANG):
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
