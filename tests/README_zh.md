# 测试

本文件夹包含客户端、服务端采集服务及 HTTP 处理器的单元测试。

项目环境与依赖安装请参见[根目录 README](../README.md) 中的“测试”章节。

## 测试结构

- `test_client.py` — 针对 `client/main.py` 的测试（配置加载、格式化、巡检流程）
- `test_server.py` — 针对 `server/agent.py` 和 `server/services/` 的测试（磁盘、CPU、内存、HTTP 处理器）

## 运行测试

```bash
python -m pytest tests/ -v
```

## 覆盖率

```bash
python -m coverage run --branch -m pytest tests/ -v
python -m coverage report --include="server/*,client/*" -m
```

以上命令与 CI 中执行的检查一致。
