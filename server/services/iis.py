#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IIS 服务信息采集（扩展示例）

IIS service information collection (extension example).

如需在巡检中增加 IIS 状态检查，请按以下步骤操作：
1. 在此文件中实现 collect() 函数
2. 在 agent.py 中导入: from services.iis import collect as collect_iis
3. 在 get_health_data() 中加入: "iis": collect_iis()
4. 在 client/main.py 中解析并展示 iis 字段

To add IIS status checks to the inspection, follow these steps:
1. Implement the collect() function in this file.
2. Import it in agent.py: from services.iis import collect as collect_iis
3. Add it in get_health_data(): "iis": collect_iis()
4. Parse and display the iis field in client/main.py.
"""


# 默认输出语言 / Default output language
DEFAULT_LANG = "zh"


def collect(lang: str = DEFAULT_LANG):
    """
    采集 IIS 运行状态。

    Collect IIS running status.

    Args:
        lang: 输出语言 (默认 zh) / Output language (default zh).

    Returns:
        dict: 包含 service_status, sites 等字段
        dict: Contains fields such as service_status and sites.
    """
    # TODO: 实现具体采集逻辑
    # TODO: implement specific collection logic
    # Windows 本地可通过 PowerShell 检查:
    # You can check locally on Windows via PowerShell:
    #   Get-Service W3SVC
    #   Import-Module WebAdministration; Get-Website
    return {
        "service_status": "unknown",
        "sites": [],
    }
