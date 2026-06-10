#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地巡检客户端配置文件

请根据实际环境修改服务器 Agent 地址和网页 URL。
"""

# 被巡检服务器 Agent 列表
# 请确保各服务器已运行 server/agent.py，且本地防火墙放通对应端口
SERVERS = [
    {
        "role": "app",          # 角色: app / db / 自定义
        "ip": "192.168.1.10",   # 服务器 IP
        "port": 5000,           # Agent 监听端口
        "name": "应用服务器-01 (Windows)",
    },
    {
        "role": "db",
        "ip": "192.168.1.20",
        "port": 5000,
        "name": "数据库服务器-01 (Windows)",
    },
    # Linux 服务器示例（同一份 agent.py 可直接运行在 Linux 上）
    # {
    #     "role": "app",
    #     "ip": "192.168.1.30",
    #     "port": 5000,
    #     "name": "应用服务器-02 (Linux)",
    # },
]

# 系统网页巡检列表
WEBS = [
    {"name": "系统登录页", "url": "http://192.168.1.100/login"},
]

# 磁盘空间告警阈值 (GB)
DISK_THRESHOLD_GB = 30
