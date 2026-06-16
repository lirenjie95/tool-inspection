# 服务器巡检 Agent（独立部署包）

此文件夹包含需要在**每台被巡检服务器**上运行的 Agent 程序。

## 原理

Agent 在服务器本地运行一个轻量 HTTP 服务，通过本机 PowerShell/df 采集磁盘等信息，
供本地巡检客户端通过 HTTP 请求查询。

## 项目结构

```
server/
├── agent.py              # HTTP 服务入口（无需修改）
├── services/             # 巡检服务扩展目录
│   ├── __init__.py
│   ├── disk.py           # 磁盘采集（已实现）
│   ├── cpu.py            # CPU 采集（已实现）
│   ├── memory.py         # 内存采集（已实现）
│   └── iis.py            # IIS 采集（扩展示例，需手动启用）
├── requirements.txt      # 零第三方依赖
└── README.md             # 本文件
```

## 部署要求

**支持平台：** Windows / Linux

**方式一：直接运行 Python（推荐开发/测试）**
- Python 3.7+（Windows 建议从官网下载安装；Linux 通常自带）
- 零第三方依赖，纯标准库实现

**方式二：打包成可执行程序（推荐生产环境）**
- 如果目标服务器**没有 Python 环境**，可使用 PyInstaller 打包
- Windows 打包为 exe，Linux 打包为 ELF
- 详见项目根目录 `scripts/README.md`

## 部署步骤

### Windows

#### 方式 A：直接运行 Python

1. 将本文件夹复制到目标服务器（通过 RDP 粘贴、共享目录或 FTP）
2. 打开命令提示符或 PowerShell，进入本文件夹：
   ```cmd
   python agent.py --port 5000
```

#### 方式 B：运行打包后的可执行程序

详见下文"打包部署"章节。

---

### Linux

#### 方式 A：直接运行 Python

1. 将本文件夹复制到目标服务器（通过 SCP、SFTP 或 rsync）：
   ```bash
   ssh user@192.168.1.30 "mkdir -p /opt/inspection-agent"
   scp -r server/* user@192.168.1.30:/opt/inspection-agent/
```
2. 运行 Agent：
   ```bash
   cd /opt/inspection-agent
   python3 agent.py --port 5000
```

#### 方式 B：systemd 后台服务（推荐）

1. 复制文件到 `/opt/inspection-agent/`
2. 创建 systemd service 文件 `/etc/systemd/system/inspection-agent.service`：
   ```ini
   [Unit]
   Description=Inspection Agent
   After=network.target

   [Service]
   Type=simple
   WorkingDirectory=/opt/inspection-agent
   ExecStart=/usr/bin/python3 /opt/inspection-agent/agent.py --port 5000
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
```
3. 启动并设置开机自启：
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now inspection-agent
   sudo systemctl status inspection-agent
```

#### 方式 C：打包成 ELF 可执行程序

如果目标服务器 Python 版本过低或没有 Python，可打包成独立 ELF：
```bash
bash scripts/build_linux.sh
```
然后将 `server/dist/inspection-agent/` 复制到目标服务器运行。
详见 `scripts/README.md`。

### 输出语言

Agent 启动/停止日志默认中文。如需输出英文：

```bash
python agent.py --port 5000 --lang en
```

---

### 启动验证

Agent 默认监听 `0.0.0.0:5000`（可通过 `--port` 修改端口）。
无论 Windows 还是 Linux，启动后在服务器本地测试：

```bash
curl http://localhost:5000/health
```

或在 Windows PowerShell 中：

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/health"
```

应返回 JSON 格式的健康数据，例如：
```json
{
  "status": "running",
  "os": "Linux",
  "disks": [
    {"DeviceID": "/", "FreeSpaceGB": 45, "SizeGB": 100},
    {"DeviceID": "/data", "FreeSpaceGB": 380, "SizeGB": 500}
  ],
  "cpu": {"usage_percent": 12.5},
  "memory": {"total_mb": 8192, "free_mb": 4096, "used_percent": 50.0}
}
```

> 轻量级存活探测可使用 `GET /ping`，返回 `{"status": "ok"}`，不执行任何采集。

### 防火墙放通

确保服务器本地防火墙允许入站连接到 Agent 端口（默认 5000）。
PowerShell 一键放行示例：

```powershell
New-NetFirewallRule -DisplayName "InspectionAgent" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow
```

## 打包部署

### Windows 打包（exe）

在开发机/打包机上执行：

```bash
pip install pyinstaller
python scripts/build_windows.py
```

将 `server/dist/inspection-agent/` **整个文件夹**复制到目标服务器：

```cmd
cd inspection-agent
start.bat          # 前台运行
start_hidden.vbs   # 后台静默运行（无黑窗口）
```

> **Windows Server 2008 兼容性提示**：打包时请使用 Python 3.7/3.8，
> 更高版本不支持 WS2008。详见 `scripts/README.md`。
>
> **复制即用（无需补丁）**：如果目标服务器无法安装 KB3063858/KB2533623 补丁，请使用：
> ```bash
> python scripts/build_windows.py --no-patch-required
> ```
> 该模式使用 Python 3.7 嵌入式运行时打包，生成的 exe 可在未打补丁的 Win7/2008 R2 上直接运行。

### Linux 打包（ELF）

```bash
bash scripts/build_linux.sh
```

将 `server/dist/inspection-agent/` 复制到目标服务器：

```bash
./start.sh --port 5000
```

打包后还会自动生成 `inspection-agent.service`，可一键注册为 systemd 服务。

---

## Windows 后台运行（可选）

**方式 A：nssm 封装为 Windows 服务（推荐）**

1. 下载 [nssm](https://nssm.cc/)
2. 以管理员执行：
   ```cmd
   nssm install InspectionAgent
   # Path: C:\Path\To\python.exe
   # Startup directory: C:\Path\To\inspection-agent\
   # Arguments: agent.py --port 5000
   nssm start InspectionAgent
```

**方式 B：计划任务**

创建计划任务，触发器选择"启动时"，操作选择启动 `python agent.py --port 5000`。

**方式 C：PowerShell 后台运行**

```powershell
Start-Process python -ArgumentList "agent.py","--port","5000" -WindowStyle Hidden
```

**方式 D：可执行程序 + start_hidden.vbs**

打包后的文件夹中包含 `start_hidden.vbs`，双击即可后台静默运行。

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

## Linux 支持说明

Agent 已完整支持 Linux。`services/disk.py` 会自动检测操作系统：
- **Windows**：通过 PowerShell 获取**所有本地磁盘**信息（自动包含 C:、D:、E: 等）
- **Linux**：通过 `df -BG` 自动采集**所有真实挂载点**（如 `/`、`/data`、`/home` 等），并过滤 `tmpfs`、`devtmpfs`、`overlay` 等伪文件系统。