# 巡检客户端

本文件夹包含本地巡检客户端。它通过 HTTP 向各服务器的 Agent 发起查询，并汇总输出巡检报告。

整体架构与部署指南请参见[项目根目录 README](../README.md)。

## 文件说明

- `main.py` — 客户端主入口
- `config.json` — 服务器 / 网页配置（运行前请先编辑）
- `requirements.txt` — Python 依赖（`requests`）

## 快速开始

1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
2. 编辑 `config.json`，填入服务器 Agent 地址。
3. 运行巡检：
   ```bash
   python main.py
   ```

## 命令行选项

所有支持的选项（包括 `--output`、`--config`、`--lang`）请参见[根目录 README](../README.md) 中的“第三步：运行巡检”章节。

## Windows 可执行文件打包

如果管理机没有 Python 环境，可将客户端打包为独立可执行文件。打包方法请参见 `../scripts/README.md`。
