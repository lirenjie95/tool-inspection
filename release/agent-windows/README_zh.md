# 巡检 Agent（Windows 版）

本压缩包包含服务器巡检 Agent 的 Windows 独立可执行文件。

## 内容说明

- `inspection-agent.exe` — 主程序
- `start.bat` — 前台运行脚本
- `start_hidden.vbs` — 后台静默运行脚本
- `_internal/scripts/check_prereqs.ps1` — 部署前兼容性检查
- `_internal/` — 运行时依赖
- `README.md` / `README_zh.md` — 使用说明

## 快速开始

1. 将 `inspection-agent` 文件夹整体复制到目标 Windows 服务器。
2. （推荐）先运行一次 `_internal/scripts/check_prereqs.ps1`，确认补丁状态。
3. 选择以下任意方式启动 Agent。

## 运行方式

- **前台运行**：双击 `start.bat`，或在命令提示符中执行：
  ```cmd
  inspection-agent.exe --port 5000
  ```
- **后台静默运行**：双击 `start_hidden.vbs`

## 配置

Agent 默认监听 `0.0.0.0:5000`。可通过 `--port` 修改端口：

```cmd
inspection-agent.exe --port 8080
```

## 确认运行状态

在 PowerShell 中执行：

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/health"
```

或使用轻量探活接口：

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/ping"
```

## 防火墙

放通 Agent 端口（默认 5000）的入站 TCP 流量：

```powershell
New-NetFirewallRule -DisplayName "InspectionAgent" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow
```

## 兼容性

- 本 CI Release 包使用 `--no-patch-required` 模式构建，可在未安装 KB3063858/KB2533623 补丁的 Windows Server 2008 R2 / Windows 7 系统上直接运行。
- 也可以不打包，直接使用 Python 源码运行 Agent；详见项目仓库说明。
