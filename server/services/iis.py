#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IIS 服务信息采集（扩展示例）

如需在巡检中增加 IIS 状态检查，请按以下步骤操作：
1. 在此文件中实现 collect() 函数
2. 在 agent.py 中导入: from services.iis import collect as collect_iis
3. 在 get_health_data() 中加入: "iis": collect_iis()
4. 在 client/main.py 中解析并展示 iis 字段
"""


def collect():
    """
    采集 IIS 运行状态。
    
    Returns:
        dict: 包含 service_status, sites 等字段
    """
    # TODO: 实现具体采集逻辑
    # Windows 本地可通过 PowerShell 检查:
    #   Get-Service W3SVC
    #   Import-Module WebAdministration; Get-Website
    return {
        "service_status": "unknown",
        "sites": [],
    }
