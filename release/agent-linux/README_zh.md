# 巡检 Agent（Linux 版）

本压缩包包含服务器巡检 Agent 的 Linux 独立可执行文件。

## 内容说明

- `inspection-agent` — ELF 可执行文件
- `start.sh` — 启动辅助脚本
- `scripts/inspection-agent.service` — systemd 服务模板
- `_internal/` — 运行时依赖
- `README.md` / `README_zh.md` — 使用说明

## 快速开始

### 前台运行

```bash
cd inspection-agent
./start.sh --port 5000
```

### systemd 后台服务

```bash
cd inspection-agent
sudo cp scripts/inspection-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now inspection-agent
sudo systemctl status inspection-agent
```

## 配置

Agent 默认监听 `0.0.0.0:5000`。可通过 `--port` 修改端口：

```bash
./inspection-agent --port 8080
```

## 确认运行状态

```bash
curl http://localhost:5000/health
```

或使用轻量探活接口：

```bash
curl http://localhost:5000/ping
```

## 防火墙

请确保目标服务器防火墙放通 Agent 端口（默认 5000）的入站 TCP 流量。

## 兼容性

- 面向 Linux x86_64 构建。
- PyInstaller 生成的可执行文件依赖构建时的 glibc 版本。为获得最佳兼容性，建议在等于或早于目标系统的环境上重新打包。
- 也可以不打包，直接使用 Python 源码运行 Agent；详见项目仓库说明。
