#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务器端巡检服务扩展包

如需新增巡检项（如 IIS、SQL Server、CPU、内存、事件日志等），
请在此目录下新建 Python 文件并实现 collect() 函数，
然后在 agent.py 中导入并加入 health 接口返回数据。
"""
