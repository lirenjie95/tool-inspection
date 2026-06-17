# 服务器巡检 Agent（Linux）

[English](README_linux.md)

此程序需要在**每台被巡检 Linux 服务器**上运行，暴露轻量 HTTP 接口供本地巡检客户端查询。

> **源码运行 vs 打包运行：** 本文档同时说明从 `server/` 源码文件夹运行，以及运行打包后的可执行文件两种方式。使用 CI Release 包时，根目录包含 `inspection-agent` ELF 可执行文件、辅助脚本 `start.sh`、systemd 服务模板，运行时依赖位于 `_internal/` 下。

## 文件说明

- `agent.py` — HTTP 服务入口（无需修改）
- `services/` — 巡检服务扩展目录
- `requirements.txt` — 零第三方依赖
- `README.md` / `README_zh.md` — 本指南

## 第一部分：使用打包好的 Release

下载 GitHub Releases 中的 `inspection-agent-linux.tar.gz` 并解压到目标服务器。

步骤：

1. 解压：

   ```bash
   tar -xzf inspection-agent-linux.tar.gz -C /opt/
   cd /opt/inspection-agent
   ```

2. 启动 Agent：

   ```bash
   ./inspection-agent --port 5000
   # 或使用辅助脚本
   ./start.sh --port 5000
   ```

3. 或注册为 systemd 后台服务：

   ```bash
   sudo cp scripts/inspection-agent.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now inspection-agent
   sudo systemctl status inspection-agent
   ```

> **兼容性提示**：PyInstaller 打包的 Linux 可执行文件依赖构建时的 glibc 版本，建议在目标系统相同或更旧的系统上打包，以确保兼容性。详见 `../scripts/README.md`。

## 第二部分：从 Python 源码运行

### 环境要求

- 目标服务器已安装 Python 3.7+
- 零第三方依赖，纯标准库实现

### 步骤

1. 将 `server/` 文件夹复制到目标服务器：

   ```bash
   ssh user@192.168.1.30 "mkdir -p /opt/inspection-agent"
   scp -r server/* user@192.168.1.30:/opt/inspection-agent/
   ```

2. 前台运行：

   ```bash
   cd /opt/inspection-agent
   python3 agent.py --port 5000
   ```

3. 或手动注册为 systemd 后台服务：

   ```bash
   sudo tee /etc/systemd/system/inspection-agent.service << 'EOF'
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
   EOF
   sudo systemctl daemon-reload
   sudo systemctl enable --now inspection-agent
   ```

## 输出语言

Agent 启动/停止日志默认中文。如需输出英文：

```bash
python3 agent.py --port 5000 --lang en
```

## 启动验证

Agent 默认监听 `0.0.0.0:5000`（可通过 `--port` 修改端口）。启动后在服务器本地测试：

```bash
curl http://localhost:5000/health
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

## 防火墙放通

确保服务器本地防火墙允许入站连接到 Agent 端口（默认 5000）。例如使用 `firewalld`：

```bash
sudo firewall-cmd --add-port=5000/tcp --permanent
sudo firewall-cmd --reload
```

或使用 `ufw`：

```bash
sudo ufw allow 5000/tcp
```

## 自行打包（可选）

如需自行构建 Linux 安装包，在打包机上执行：

```bash
pip install pyinstaller
bash scripts/build_linux.sh
```

然后将 `server/dist/inspection-agent/` 整个文件夹复制到目标服务器。详见 `../scripts/README.md`。

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

如需新增巡检项（如 Nginx、MySQL、事件日志等；CPU、内存、磁盘已内置），请按以下步骤：

1. **新建服务文件**

   在 `services/` 下新建文件，例如 `services/mysql.py`：

   ```python
   def collect():
       # 实现采集逻辑
       return {"status": "ok", "databases": [...]}
   ```

2. **注册到 Agent**

   在 `agent.py` 顶部导入：

   ```python
   from services.mysql import collect as collect_mysql
   ```

   在 `get_health_data()` 中加入：

   ```python
   data["mysql"] = _safe_collect("mysql", collect_mysql)
   ```

   现有内置服务（disk / cpu / memory）也是通过 `_safe_collect` 调用的，新增服务建议保持同样写法。

   > `_safe_collect()` 会隔离单个采集服务的异常，避免某个服务失败导致整体 `/health` 接口不可用。

3. **客户端展示**

   在 `client/main.py` 中解析并展示新增的 `mysql` 字段。

## Linux 支持说明

Agent 已完整支持 Linux。`services/disk.py` 会自动检测操作系统，通过 `df -BG` 自动采集**所有真实挂载点**（如 `/`、`/data`、`/home` 等），并过滤 `tmpfs`、`devtmpfs`、`overlay` 等伪文件系统。
