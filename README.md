# 服务器巡检脚本（Agent-Client 架构）

针对内网 Windows 服务器的轻量级巡检工具，采用 **Agent-Client** 模式，
无需 SSH/WinRM/WMI 等复杂远程协议。

## 架构说明

```
┌─────────────────┐      HTTP (内网)      ┌─────────────────┐
│   本地客户端     │  ──────────────────>  │  服务器 Agent   │
│  client/main.py │    GET /health        │ server/agent.py │
└─────────────────┘                       └─────────────────┘
       │                                          │
       │ 汇总输出                                  │ 本地 PowerShell/df
       ▼                                          ▼
   巡检报告                                    磁盘数据
```

**优势：**
- 服务器端**零第三方依赖**，纯 Python 标准库
- 无需开放 SSH/WinRM，只需一个 HTTP 端口
- 服务器本地采集，数据准确
- **完整支持 Windows / Linux**，同一份代码跨平台运行
- 新增服务只需在 `server/services/` 下新建文件

## 项目结构

```
.
├── client/                    # 本地巡检端（只需在一台管理机上运行）
│   ├── main.py               # 巡检主入口
│   ├── config.py             # 服务器 Agent 地址配置
│   └── requirements.txt      # pip install -r requirements.txt
├── server/                    # 服务器 Agent（每台被巡检服务器部署）
│   ├── agent.py              # HTTP 服务入口（纯标准库）
│   ├── services/             # 巡检服务扩展目录
│   │   ├── disk.py           # 磁盘采集（已实现）
│   │   └── iis.py            # IIS 采集（扩展示例）
│   ├── requirements.txt      # 零依赖
│   └── README.md             # Agent 部署说明
├── scripts/                   # 打包脚本
│   ├── build_windows.py      # Windows exe 打包
│   ├── build_linux.sh        # Linux ELF 打包
│   └── README.md             # 打包说明
├── tests/                     # 单元测试
│   ├── __init__.py
│   ├── test_client.py
│   └── test_server.py
├── .github/
│   └── workflows/
│       └── ci-cd.yml          # GitHub Actions CI/CD
└── README.md                 # 本文件
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

1. 在开发机上打包：
   ```bash
   pip install pyinstaller
   python scripts/build_windows.py
   ```
2. 将 `server/dist/inspection-agent/` **整个文件夹**复制到目标服务器
3. 运行 `start.bat`（前台）或 `start_hidden.vbs`（后台静默）

> Windows Server 2008 兼容性：打包时请使用 Python 3.7/3.8，
> 更高版本不支持 WS2008。详见 `scripts/README.md`。

**防火墙放行（两种方式都需要）：**

```powershell
New-NetFirewallRule -DisplayName "InspectionAgent" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow
```

> 详细部署方式（后台服务、计划任务、nssm 等）请参考 `server/README.md`

### 第二步：在本地配置客户端

1. 安装依赖：
   ```bash
   pip install -r client/requirements.txt
   ```

2. 编辑 `client/config.py`，填入各服务器的 Agent 地址：
   ```python
   SERVERS = [
       {"role": "app", "ip": "192.168.1.10", "port": 5000, "name": "应用服务器-01"},
       {"role": "db",  "ip": "192.168.1.20", "port": 5000, "name": "数据库服务器-01"},
   ]
   WEBS = [
       {"name": "系统登录页", "url": "http://192.168.1.100/login"},
   ]
   ```

### 第三步：运行巡检

```bash
cd client
python main.py
```

### 输出示例

```
============================================================
服务器巡检开始
============================================================

【应用服务器巡检】
192.168.1.10 C盘剩余：45 GB D盘剩余：120 GB
  -> 状态: 运行正常
  -> 磁盘检查: 通过

【数据库服务器巡检】
192.168.1.20 C盘剩余：28 GB D盘剩余：200 GB
  -> 状态: 运行正常
  -> [告警] 磁盘低于阈值 (30GB)

【系统网页巡检】
系统登录页 (http://192.168.1.100/login)
  -> 状态: 正常打开 (HTTP 200)

============================================================
巡检结果汇总
============================================================
共发现 1 项异常，请处理：
   - 数据库服务器 192.168.1.20: 磁盘空间不足
============================================================
```

## 扩展指南

### 新增服务器

只需在 `client/config.py` 的 `SERVERS` 列表中添加 IP 和端口，
并在对应服务器上启动 `server/agent.py` 即可。

### 新增巡检服务（如 IIS、SQL Server、CPU、内存）

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
           "disks": collect_disk(),
       }
       data["sqlserver"] = collect_sqlserver()
       return data
   ```

**客户端扩展：**

在 `client/main.py` 中解析服务端返回的新字段并展示。

### Linux 服务器支持

同一份 `server/agent.py` 可直接运行在 Linux 上，自动通过 `df -BG` 采集 `/` 和 `/data` 磁盘信息。

**部署方式：**

```bash
# 1. 复制到目标服务器
scp -r server/ user@192.168.1.30:/opt/inspection-agent

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

## 故障排查

| 现象 | 排查步骤 |
|------|---------|
| 客户端连接超时 | 确认 Agent 已启动；检查服务器防火墙是否放行端口；确认内网互通 |
| Agent 启动报错 | 确认 Python 版本 >= 3.7；确认当前目录下有 `services/` 文件夹 |
| 磁盘数据为空 | 确认 PowerShell 可正常执行；确认 C:/D: 盘存在 |
| 网页检测失败 | 确认 URL 正确；确认本地网络可访问目标网页 |

## 安全建议

- Agent 默认监听 `0.0.0.0`，建议**仅在内网使用**，不要暴露到公网
- 如需更高安全性，可在 Agent 前加 Nginx/iptables 限制访问源 IP
- Windows 生产环境建议封装为 Windows Service；Linux 建议使用 systemd
- 密码等敏感信息不要硬编码在脚本中，建议使用环境变量传入
