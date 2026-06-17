# 巡检客户端（Windows 版）

本压缩包包含本地巡检客户端的 Windows 独立可执行文件。它会向各服务器的 Agent 发起查询，并汇总输出巡检报告。

## 内容说明

- `inspection-client.exe` — 客户端主程序
- `config.json` — 服务器 / 网页配置（运行前请先编辑）
- `start.bat` — 运行并在控制台输出文本报告
- `start_json.bat` — 运行并保存 `report.json`
- `start_txt.bat` — 运行并保存 `report.txt`
- `_internal/` — 运行时依赖
- `README.md` / `README_zh.md` — 使用说明

## 快速开始

1. 将 `inspection-client` 文件夹整体复制到 Windows 管理机。
2. 编辑 `config.json`，填入待巡检服务器的 Agent 地址：
   ```json
   {
     "LANGUAGE": "zh",
     "SERVERS": [
       {"role": "app", "ip": "192.168.1.10", "port": 5000, "name": "应用服务器-01"},
       {"role": "db",  "ip": "192.168.1.20", "port": 5000, "name": "数据库服务器-01"}
     ],
     "WEBS": [
       {"name": "系统登录页", "url": "http://192.168.1.100/login"}
     ],
     "DISK_THRESHOLD_GB": 30
   }
   ```
3. 双击 `start.bat` 运行巡检。

## 输出模式

- `start.bat` — 在控制台窗口输出报告
- `start_json.bat` — 将结构化报告保存到 `report.json`
- `start_txt.bat` — 将文本报告保存到 `report.txt`

## 输出语言

在 `config.json` 中设置 `"LANGUAGE": "en"` 输出英文，或 `"LANGUAGE": "zh"` 输出中文。

## 兼容性

- 本 CI Release 包使用 `--no-patch-required` 模式构建，可在未安装 KB3063858/KB2533623 补丁的 Windows Server 2008 R2 / Windows 7 系统上直接运行。
- 也可以不打包，直接使用 Python 源码运行客户端；详见项目仓库说明。
