# Inspection Agent (Linux)

[中文文档](README_zh.md)

This package contains the standalone Linux executable for the Server Inspection Agent.

## Contents

- `inspection-agent` — ELF executable
- `start.sh` — Helper startup script
- `scripts/inspection-agent.service` — systemd service template
- `_internal/` — Runtime dependencies
- `README.md` / `README_zh.md` — This documentation

## Quick Start

### Foreground

```bash
cd inspection-agent
./start.sh --port 5000
```

### systemd Background Service

```bash
cd inspection-agent
sudo cp scripts/inspection-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now inspection-agent
sudo systemctl status inspection-agent
```

## Configuration

The Agent listens on `0.0.0.0:5000` by default. Change the port with `--port`:

```bash
./inspection-agent --port 8080
```

## Verify It Is Running

```bash
curl http://localhost:5000/health
```

Or use the lightweight probe:

```bash
curl http://localhost:5000/ping
```

## Firewall

Make sure the target server's firewall allows inbound TCP traffic on the Agent port (default 5000).

## Compatibility

- Built for Linux x86_64.
- PyInstaller executables depend on the glibc version used at build time. For maximum compatibility, build on a system that is the same age as or older than the target system.
- The Agent itself can also be run directly from Python source without packaging; see the project repository for details.
