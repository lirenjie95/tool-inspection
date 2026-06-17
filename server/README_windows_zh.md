# 服务器巡检 Agent（Windows）

[English](README_windows.md)

此程序需要在**每台被巡检 Windows 服务器**上运行，暴露轻量 HTTP 接口供本地巡检客户端查询。

> **源码运行 vs 打包运行：** 本文档同时说明从 `server/` 源码文件夹运行，以及运行打包后的可执行文件两种方式。使用 CI Release 包时，根目录包含 `inspection-agent.exe`、辅助启动脚本（`start.bat`、`start_hidden.vbs` 等），运行时依赖位于 `_internal/` 下。

## 文件说明

- `agent.py` — HTTP 服务入口（无需修改）
- `services/` — 巡检服务扩展目录
- `requirements.txt` — 零第三方依赖
- `README.md` / `README_zh.md` — 本指南

## 第一部分：使用打包好的 Release

下载 GitHub Releases 中的 `inspection-agent-windows.zip` 并解压到目标服务器。包根目录包含：

- `inspection-agent.exe` — 主程序
- `start.bat` — 前台运行脚本
- `start_hidden.vbs` — 后台静默运行脚本（无黑窗口）
- `_internal/` — 运行时依赖与 `scripts/check_prereqs.ps1`

步骤：

1. （推荐）先在目标服务器运行一次 `_internal/scripts/check_prereqs.ps1`，检查补丁状态。
2. 启动 Agent：

   ```cmd
   inspection-agent.exe --port 5000
   start.bat          # 前台运行
   start_hidden.vbs   # 后台静默运行
   ```

> **Windows Server 2008 兼容性提示**：CI Release 包使用 Python 3.7 嵌入式运行时，可在未打补丁的 Windows Server 2008 R2 / Windows 7 上直接运行。如需自行打包，请使用 Python 3.7/3.8 面向 WS2008 目标。详见 `../scripts/README.md`。

## 第二部分：从 Python 源码运行

### 环境要求

- 目标服务器已安装 Python 3.7+
- 零第三方依赖，纯标准库实现

### 步骤

1. 将本文件夹复制到目标服务器（通过 RDP 粘贴、共享目录或 FTP）。
2. 启动 Agent：

   ```cmd
   cd server
   python agent.py --port 5000
   ```

## 输出语言

Agent 启动/停止日志默认中文。如需输出英文：

```cmd
python agent.py --port 5000 --lang en
```

## 启动验证

Agent 默认监听 `0.0.0.0:5000`（可通过 `--port` 修改端口）。启动后在服务器本地测试：

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/health"
```

应返回 JSON 格式的健康数据，例如：

```json
{
  "status": "running",
  "os": "Windows",
  "disks": [
    {"DeviceID": "C:", "FreeSpaceGB": 45, "SizeGB": 100},
    {"DeviceID": "D:", "FreeSpaceGB": 120, "SizeGB": 200}
  ],
  "cpu": {"usage_percent": 12.5},
  "memory": {"total_mb": 8192, "free_mb": 4096, "used_percent": 50.0}
}
```

> 轻量级存活探测可使用 `GET /ping`，返回 `{"status": "ok"}`，不执行任何采集。

## 防火墙放通

确保服务器本地防火墙允许入站连接到 Agent 端口（默认 5000）。PowerShell 一键放行示例：

```powershell
New-NetFirewallRule -DisplayName "InspectionAgent" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow
```

## Windows 后台运行（可选）

**方式 A：nssm 封装为 Windows 服务（推荐）**

1. 下载 [nssm](https://nssm.cc/)
2. 以管理员执行：

   ```cmd
   nssm install InspectionAgent
   # 路径: C:\Path\To\python.exe
   # 启动目录: C:\Path\To\inspection-agent\
   # 参数: agent.py --port 5000
   nssm start InspectionAgent
   ```

**方式 B：计划任务**

创建计划任务，触发器选择“启动时”，操作选择启动 `python agent.py --port 5000`。

**方式 C：PowerShell 后台运行**

```powershell
Start-Process python -ArgumentList "agent.py","--port","5000" -WindowStyle Hidden
```

**方式 D：可执行程序 + start_hidden.vbs**

打包后的文件夹中包含 `start_hidden.vbs`，双击即可后台静默运行。

## 自行打包（可选）

如需自行构建 Windows 安装包，在打包机上执行：

```bash
pip install pyinstaller
python scripts/build_windows.py
```

然后将 `server/dist/inspection-agent/` 整个文件夹复制到目标服务器。详见 `../scripts/README.md`，包括面向未打补丁老系统的 `--no-patch-required` 模式。

## 接口说明

### GET /health

返回当前服务器健康状态。

**响应字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | 服务状态，通常为 "running" |
| os | string | 操作系统类型 "Windows" / "Linux" |
| disks | list | 磁盘列表，含 DeviceID, FreeSpaceGB, SizeGB；客户端会汇总所有磁盘的 FreeSpaceGB 进行总空间阈值判断 |
| cpu | dict | CPU 使用率，含 usage_percent |
| memory | dict | 内存使用情况，含 total_mb, free_mb, used_percent |

### GET /ping

轻量级存活探测，不执行任何采集，返回：

```json
{"status": "ok"}
```

## 扩展服务

如需新增巡检项（如 IIS、SQL Server、事件日志等；CPU、内存、磁盘已内置），请按以下步骤：

1. **新建服务文件**

   在 `services/` 下新建文件，例如 `services/sqlserver.py`：

   ```python
   def collect():
       # 实现采集逻辑
       return {"status": "ok", "databases": [...]}
   ```

2. **注册到 Agent**

   在 `agent.py` 顶部导入：

   ```python
   from services.sqlserver import collect as collect_sqlserver
   ```

   在 `get_health_data()` 中加入：

   ```python
   data["sqlserver"] = _safe_collect("sqlserver", collect_sqlserver)
   ```

   现有内置服务（disk / cpu / memory）也是通过 `_safe_collect` 调用的，新增服务建议保持同样写法。

   > `_safe_collect()` 会隔离单个采集服务的异常，避免某个服务失败导致整体 `/health` 接口不可用。

3. **客户端展示**

   在 `client/main.py` 中解析并展示新增的 `sqlserver` 字段。
