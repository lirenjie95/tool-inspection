# Server Inspection Agent (Windows)

[中文文档](README_windows_zh.md)

This is the Agent program that runs on **each Windows server being inspected**. It exposes a lightweight HTTP interface for the local inspection client to query.

> **Source vs. Packaged:** This README describes both running from the `server/` source folder and running a packaged executable. When using a CI release package, the root contains `inspection-agent.exe`, helper scripts (`start.bat`, `start_hidden.vbs`), and runtime dependencies under `_internal/`.

## Files

- `agent.py` — HTTP service entry point (no modification needed)
- `services/` — Inspection service extension directory
- `requirements.txt` — Zero third-party dependencies
- `README.md` / `README_zh.md` — This guide

## Part 1: Use the Packaged Release

Download `inspection-agent-windows.zip` from GitHub Releases and extract it on the target server. The package root contains:

- `inspection-agent.exe` — Main program
- `start.bat` — Foreground run script
- `start_hidden.vbs` — Background silent run script (no black window)
- `_internal/` — Runtime dependencies and `scripts/check_prereqs.ps1`

Steps:

1. (Recommended) Run `_internal/scripts/check_prereqs.ps1` once to verify the patch status of the target server.
2. Start the Agent:

   ```cmd
   inspection-agent.exe --port 5000
   start.bat          # foreground
   start_hidden.vbs   # background silent
   ```

> **Windows Server 2008 Compatibility Tip**: The CI Release package uses Python 3.7 embedded runtime and can run directly on unpatched Windows Server 2008 R2 / Windows 7. If you build the package yourself, use Python 3.7/3.8 for WS2008 targets. See `../scripts/README.md` for details.

## Part 2: Run from Python Source

### Requirements

- Python 3.7+ installed on the target server
- Zero third-party dependencies; pure standard library implementation

### Steps

1. Copy the `server/` folder to the target server (via RDP paste, shared folder, or FTP).
2. Start the Agent:

   ```cmd
   cd server
   python agent.py --port 5000
   ```

## Output Language

The Agent's startup/shutdown logs default to Chinese. To output them in English:

```cmd
python agent.py --port 5000 --lang en
```

## Startup Verification

The Agent listens on `0.0.0.0:5000` by default (the port can be changed via `--port`). After starting, test locally on the server:

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/health"
```

It should return health data in JSON format, for example:

```json
{
  "status": "running",
  "os": "Windows",
  "disks": [
    {"DeviceID": "C:", "FreeSpaceGB": 45, "SizeGB": 100},
    {"DeviceID": "D:", "FreeSpaceGB": 120, "SizeGB": 200}
  ],
  "cpu": {"usage_percent": 12.5},
  "memory": {"total_mb": 8192, "free_mb": 4096, "used_percent": 50.0}
}
```

> For a lightweight liveness probe, use `GET /ping`, which returns `{"status": "ok"}` without performing any collection.

## Firewall Rule

Make sure the local server firewall allows inbound connections to the Agent port (default 5000). One-click PowerShell allow rule:

```powershell
New-NetFirewallRule -DisplayName "InspectionAgent" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow
```

## Run in the Background (Optional)

**Option A: Wrap as a Windows Service with nssm (Recommended)**

1. Download [nssm](https://nssm.cc/)
2. Run as administrator:

   ```cmd
   nssm install InspectionAgent
   # Path: C:\Path\To\python.exe
   # Startup directory: C:\Path\To\inspection-agent\
   # Arguments: agent.py --port 5000
   nssm start InspectionAgent
   ```

**Option B: Scheduled Task**

Create a scheduled task with the trigger set to "At startup" and the action set to start `python agent.py --port 5000`.

**Option C: Run in Background via PowerShell**

```powershell
Start-Process python -ArgumentList "agent.py","--port","5000" -WindowStyle Hidden
```

**Option D: Packaged Executable + start_hidden.vbs**

The packaged folder contains `start_hidden.vbs`; double-click it to run silently in the background.

## Packaging from Source (Optional)

If you need to build the Windows package yourself, run on the packaging machine:

```bash
pip install pyinstaller
python scripts/build_windows.py
```

Then copy the entire `server/dist/inspection-agent/` folder to the target server. See `../scripts/README.md` for details, including `--no-patch-required` mode for unpatched legacy systems.

## API Reference

### GET /health

Returns the current health status of the server.

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| status | string | Service status, usually "running" |
| os | string | Operating system type "Windows" / "Linux" |
| disks | list | Disk list containing DeviceID, FreeSpaceGB, SizeGB; the client sums FreeSpaceGB across all disks for total space threshold evaluation |
| cpu | dict | CPU usage, containing usage_percent |
| memory | dict | Memory usage, containing total_mb, free_mb, used_percent |

### GET /ping

Lightweight liveness probe; does not perform any collection, returns:

```json
{"status": "ok"}
```

## Extending Services

To add new inspection items (such as IIS, SQL Server, event logs, etc.; CPU, memory, and disk are already built-in), follow these steps:

1. **Create a service file**

   Create a new file under `services/`, for example `services/sqlserver.py`:

   ```python
   def collect():
       # Implement collection logic
       return {"status": "ok", "databases": [...]}
   ```

2. **Register with the Agent**

   Import at the top of `agent.py`:

   ```python
   from services.sqlserver import collect as collect_sqlserver
   ```

   Add to `get_health_data()`:

   ```python
   data["sqlserver"] = _safe_collect("sqlserver", collect_sqlserver)
   ```

   The existing built-in services (disk / cpu / memory) are also called via `_safe_collect`; new services should follow the same pattern.

   > `_safe_collect()` isolates exceptions from individual collection services, preventing a single service failure from rendering the entire `/health` endpoint unavailable.

3. **Display on the client**

   Parse and display the new `sqlserver` field in `client/main.py`.
