# Inspection Agent (Windows)

[中文文档](README_zh.md)

This package contains the standalone Windows executable for the Server Inspection Agent.

## Contents

- `inspection-agent.exe` — Main executable
- `start.bat` — Foreground run script
- `start_hidden.vbs` — Background silent run script
- `_internal/scripts/check_prereqs.ps1` — Pre-deployment compatibility check
- `_internal/` — Runtime dependencies
- `README.md` / `README_zh.md` — This documentation

## Quick Start

1. Copy the entire `inspection-agent` folder to the target Windows server.
2. (Recommended) Run `_internal/scripts/check_prereqs.ps1` once to verify patch status.
3. Start the Agent using one of the methods below.

## Run Methods

- **Foreground**: double-click `start.bat` or run from Command Prompt:
  ```cmd
  inspection-agent.exe --port 5000
  ```
- **Background silently**: double-click `start_hidden.vbs`

## Configuration

The Agent listens on `0.0.0.0:5000` by default. Change the port with `--port`:

```cmd
inspection-agent.exe --port 8080
```

## Verify It Is Running

In PowerShell:

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/health"
```

Or use the lightweight probe:

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/ping"
```

## Firewall

Allow inbound TCP traffic on the Agent port (default 5000):

```powershell
New-NetFirewallRule -DisplayName "InspectionAgent" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow
```

## Compatibility

- This CI Release package is built with `--no-patch-required`, so it can run directly on Windows Server 2008 R2 / Windows 7 systems without the KB3063858/KB2533623 patches.
- The Agent itself can also be run directly from Python source without packaging; see the project repository for details.
