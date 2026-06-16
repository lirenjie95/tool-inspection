# 服务器巡检脚本（Agent-Client 架构）

针对内网 Windows 服务器的轻量级巡检工具，采用 **Agent-Client** 模式，
无需 SSH/WinRM/WMI 等复杂远程协议。

## 架构说明

```
┌─────────────────┐      HTTP (内网)      ┌─────────────────┐
│   本地客户端     │  ──────────────────>  │  服务器 Agent   │
│  client/main.py │  GET /health /ping    │ server/agent.py │
└─────────────────┘                       └─────────────────┘
       │                                          │
       │ 汇总输出                                  │ 本地 PowerShell/df/free
       ▼                                          ▼
   巡检报告                                CPU / 内存 / 磁盘数据
```

**优势：**
- 服务器端**零第三方依赖**，纯 Python 标准库
- 无需开放 SSH/WinRM，只需一个 HTTP 端口
- 服务器本地采集，数据准确
- **完整支持 Windows / Linux**，同一份代码跨平台运行
- **内置 CPU / 内存 / 磁盘采集**，开箱即用
- 新增服务只需在 `server/services/` 下新建文件

## 项目结构

```
.
├── client/                     # 本地巡检端（只需在一台管理机上运行）
│   ├── main.py                 # 巡检主入口
│   ├── config.json             # 服务器 Agent 地址配置
│   └── requirements.txt        # pip install -r requirements.txt
├── server/                     # 服务器 Agent（每台被巡检服务器部署）
│   ├── agent.py                # HTTP 服务入口（纯标准库）
│   ├── services/               # 巡检服务扩展目录
│   │   ├── __init__.py
│   │   ├── disk.py             # 磁盘采集（已实现）
│   │   ├── cpu.py              # CPU 采集（已实现）
│   │   ├── memory.py           # 内存采集（已实现）
│   │   └── iis.py              # IIS 采集（扩展示例，需手动启用）
│   ├── requirements.txt        # 零依赖
│   └── README.md               # Agent 部署说明
├── scripts/                    # 打包脚本
│   ├── build_windows.py        # 服务器 Windows exe 打包
│   ├── build_client_windows.py # 客户端 Windows exe 打包
│   ├── build_linux.sh          # Linux ELF 打包
│   └── README.md               # 打包说明
├── tests/                      # 单元测试
│   ├── __init__.py
│   ├── test_client.py
│   └── test_server.py
├── .github/
│   └── workflows/
│       └── ci-cd.yml           # GitHub Actions CI/CD
└── README.md                   # 本文件
```

## 环境要求

| 组件 | 要求 |
|------|------|
| Python | 3.7+ |
| 服务器端 | 无需第三方库，纯标准库 |
| 客户端 | 仅需 `requests` |
| 网络 | 内网互通，Agent 端口放通 |

## 快速开始

### 第一步：在每台服务器上部署 Agent

根据目标服务器是否有 Python 环境，选择以下方式之一：

**方式 A：直接运行 Python（服务器已安装 Python 3.7+）**

1. 将 `server/` 文件夹完整复制到目标服务器（通过 RDP 粘贴或共享目录）
2. 启动 Agent：
   ```cmd
   cd server
   python agent.py --port 5000
   ```

**方式 B：打包成可执行程序（服务器无 Python 环境，推荐）**

本项目默认面向 **Windows Server 2008 R2 Enterprise** 打包，要求打包机使用 **Python 3.8.x**。

1. 在开发机上打包：
   ```bash
   pip install pyinstaller
   python scripts/build_windows.py
   ```
2. 将 `server/dist/inspection-agent/` **整个文件夹**复制到目标服务器
3. 运行 `start.bat`（前台）或 `start_hidden.vbs`（后台静默）

> 如果当前 Python 版本高于 3.8.x，脚本会报错并提示原因。
> 若目标服务器为 Windows Server 2012+ / Win8.1+，可使用 `python scripts/build_windows.py --target modern`。
> **若目标服务器无法安装系统补丁（如 KB3063858），但必须是 Win7/2008 R2，请使用：**
> ```bash
> python scripts/build_windows.py --no-patch-required
> ```
> 该模式会自动下载 Python 3.7 嵌入式运行时打包，生成的 exe 可在未打补丁的老系统上直接运行。
> 详见 `scripts/README.md`。

**防火墙放行（两种方式都需要）：**

```powershell
New-NetFirewallRule -DisplayName "InspectionAgent" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow
```

> 详细部署方式（后台服务、计划任务、nssm 等）请参考 `server/README.md`

**Agent 接口：**

- `GET /health`：返回完整健康数据（磁盘、CPU、内存等）
- `GET /ping`：轻量级存活探测，返回 `{"status": "ok"}`

### 第二步：在本地配置客户端

1. 安装依赖：
   ```bash
   pip install -r client/requirements.txt
   ```

2. 编辑 `client/config.json`，填入各服务器的 Agent 地址：
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
     "DISK_THRESHOLD_GB": 30,
     "ROLE_DISK_THRESHOLDS_GB": {
       "db": 30
     }
   }
   ```

   > 说明：`LANGUAGE` 默认为 `"zh"`（中文），设置为 `"en"` 可输出英文巡检报告。
   > `DISK_THRESHOLD_GB` 按单台服务器的**总剩余磁盘空间**判断。例如上例中
   > 默认阈值 30GB 表示该服务器所有磁盘剩余空间之和需 ≥30GB；数据库角色同样要求
   > 总剩余空间 ≥30GB。如需为数据库角色设置更高阈值，可调整 `ROLE_DISK_THRESHOLDS_GB.db`。

### 第三步：运行巡检

```bash
cd client
python main.py

# 保存文本报告
python main.py --output report.txt

# 保存 JSON 报告（方便二次处理）
python main.py --output report.json

# 使用自定义配置文件（适合多环境：测试/生产）
# 支持 .json 与 .py 两种格式
python main.py --config config_prod.json
python main.py --config config_prod.py

# 输出英文报告（覆盖配置文件中的 LANGUAGE）
python main.py --lang en
```

### 输出示例

> 以下示例使用默认磁盘阈值 30GB。若配置了 `ROLE_DISK_THRESHOLDS_GB`，会按对应角色的阈值判断。
> 输出会按 `role` 字段对服务器分组展示（如 `app`、`db`），未匹配到预定义角色名时显示为 `{role} 服务器巡检`。

```
============================================================
服务器巡检开始
============================================================

【应用服务器巡检】
应用服务器-01 (192.168.1.10) C盘剩余：20 GB D盘剩余：20 GB
  -> 状态: 运行正常
  -> CPU: 35%, 内存: 62%
  -> 总磁盘空间检查: 通过

【数据库服务器巡检】
数据库服务器-01 (192.168.1.20) C盘剩余：10 GB D盘剩余：15 GB
  -> 状态: 运行正常
  -> CPU: 45%, 内存: 78%
  -> [告警] 总磁盘空间低于阈值 (30GB)

【系统网页巡检】
系统登录页 (http://192.168.1.100/login)
  -> 状态: 正常打开 (HTTP 200)

============================================================
巡检结果汇总
============================================================
共发现 1 项异常，请处理：
   - 数据库服务器-01 (192.168.1.20): 总磁盘空间不足
============================================================
```

### 第四步：打包客户端为 Windows 可执行程序（可选）

如果管理机没有 Python 环境，可将客户端打包为独立 exe：

```bash
pip install pyinstaller
python scripts/build_client_windows.py
```

打包完成后，输出位于 `client/dist/inspection-client/`，包含：
- `inspection-client.exe` — 客户端主程序
- `config.json` — 默认配置文件（可直接修改）
- `start.bat` — 前台运行脚本
- `start_json.bat` — 运行并输出 JSON 报告
- `start_txt.bat` — 运行并输出文本报告

部署方式：将 `client/dist/inspection-client/` **整个文件夹**复制到目标 Windows 管理机，
编辑 `config.json` 后双击 `start.bat` 即可运行。

> CI/CD 已同步支持：推送 `v*` 标签时会自动构建 `inspection-client-windows.zip`
> 并上传到 GitHub Release。

## 扩展指南

### 新增服务器

只需在 `client/config.json` 的 `SERVERS` 列表中添加 IP 和端口，
并在对应服务器上启动 `server/agent.py` 即可。

### 新增巡检服务（如 IIS、SQL Server）

**服务端扩展：**

1. 在 `server/services/` 下新建文件，例如 `sqlserver.py`：
   ```python
   def collect():
       # 实现采集逻辑
       return {"status": "ok", "databases": [...]}
   ```

2. 在 `server/agent.py` 中导入并注册：
   ```python
   from services.sqlserver import collect as collect_sqlserver
   
   def get_health_data():
       data = {
           "status": "running",
           "os": platform.system(),
           "disks": _safe_collect("disk", collect_disk),
           "cpu": _safe_collect("cpu", collect_cpu),
           "memory": _safe_collect("memory", collect_memory),
       }
       data["sqlserver"] = _safe_collect("sqlserver", collect_sqlserver)
       return data
   ```

   > `_safe_collect()` 会隔离单个采集服务的异常，避免新增服务失败影响整体 `/health` 接口。

**客户端扩展：**

在 `client/main.py` 中解析并展示服务端返回的新字段。通常需要同时修改两处：

1. **文本输出**：在 `inspect_server()` 的 `if data.get("_http_ok")` 分支中，
   使用 `lines.append(...)` 加入新字段的格式化输出。
2. **结构化数据**：在 `run_inspection()` 中，将新字段写入 `structured["servers"][srv["ip"]]["data"]`，
   这样 `--output report.json` 生成的 JSON 报告也会包含该字段。

> **注意：** CPU、内存、磁盘已作为内置服务实现，分别位于 `server/services/cpu.py`、
> `server/services/memory.py`、`server/services/disk.py`，无需额外扩展即可使用。

### Linux 服务器支持

同一份 `server/agent.py` 可直接运行在 Linux 上，自动通过 `df -BG` 采集所有真实挂载点（如 `/`、`/data`、`/home` 等），并自动过滤 `tmpfs`、`devtmpfs` 等伪文件系统。

**部署方式：**

```bash
# 1. 复制到目标服务器
ssh user@192.168.1.30 "mkdir -p /opt/inspection-agent"
scp -r server/* user@192.168.1.30:/opt/inspection-agent/

# 2. 前台运行
python3 /opt/inspection-agent/agent.py --port 5000

# 3. 或注册为 systemd 服务
sudo tee /etc/systemd/system/inspection-agent.service << 'EOF'
[Unit]
Description=Inspection Agent
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/inspection-agent/agent.py --port 5000
Restart=always

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable --now inspection-agent
```

**无 Python 环境？打包成 ELF：**

```bash
bash scripts/build_linux.sh
```

打包后会生成 `inspection-agent` ELF 可执行文件和 systemd service 模板，
和 Windows exe 一样无需目标机安装 Python。详见 `scripts/README.md`。

## 测试

项目包含 `tests/test_client.py` 和 `tests/test_server.py`，覆盖客户端配置加载、
服务器巡检判断、Agent 接口以及各采集服务的主要分支。

> 提示：以下命令使用 `python`，在某些系统（如 macOS）上可能需要替换为 `python3`。

```bash
# 安装测试依赖
python -m pip install pytest coverage
python -m pip install -r client/requirements.txt

# 运行全部测试
python -m pytest tests/ -v

# 查看覆盖率（与 CI 保持一致）
python -m coverage run --branch -m pytest tests/ -v
python -m coverage report --include="server/*,client/*" -m
```

> 提示：`tests/test_server.py` 中的 HTTP Handler 测试会启动真实 HTTP 服务，
> 使用临时端口，无需手动启动 Agent。

## 输出语言

本项目所有命令行工具默认输出**中文**，同时支持切换到**英文**。

- **客户端巡检报告**
  - 在 `client/config.json` 中设置 `"LANGUAGE": "en"`，或
  - 使用 `python main.py --lang en`

- **Agent 启动日志**
  - `python agent.py --port 5000 --lang en`

- **Windows 打包脚本**
  - `python scripts/build_windows.py --lang en`
  - `python scripts/build_client_windows.py --lang en`

- **Linux 打包脚本**
  - `OUTPUT_LANG=en bash scripts/build_linux.sh`

## 故障排查

| 现象 | 排查步骤 |
|------|---------|
| 客户端连接超时 | 确认 Agent 已启动；检查服务器防火墙是否放行端口；确认内网互通 |
| Agent 启动报错 | 确认 Python 版本 >= 3.7；确认当前目录下有 `services/` 文件夹 |
| 磁盘数据为空 | 确认 PowerShell 可正常执行；确认存在本地磁盘 |
| 网页检测失败 | 确认 URL 正确；确认本地网络可访问目标网页 |
| 启动报 `_socket: 参数错误` | 老系统（Win7/2008 R2）缺少 KB3063858 补丁；如无法安装补丁，请用 `--no-patch-required` 模式重新打包 |

## 安全建议

- Agent 默认监听 `0.0.0.0`，建议**仅在内网使用**，不要暴露到公网
- 如需更高安全性，可在 Agent 前加 Nginx/iptables 限制访问源 IP
- Windows 生产环境建议封装为 Windows Service；Linux 建议使用 systemd
- 密码等敏感信息不要硬编码在脚本中，建议使用环境变量传入
