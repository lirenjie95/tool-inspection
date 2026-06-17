# Tests

[中文文档](README_zh.md)

This folder contains unit tests for the client, server services, and HTTP handler.

For project setup and dependency installation, see the [Testing section in the root README](../README.md).

## Test Structure

- `test_client.py` — Tests for `client/main.py` (configuration loading, formatting, inspection flow)
- `test_server.py` — Tests for `server/agent.py` and `server/services/` (disk, CPU, memory, HTTP handler)

## Running Tests

```bash
python -m pytest tests/ -v
```

## Coverage

```bash
python -m coverage run --branch -m pytest tests/ -v
python -m coverage report --include="server/*,client/*" -m
```

These commands match the checks run in CI.
