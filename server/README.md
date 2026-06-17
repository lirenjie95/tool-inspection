# Server Inspection Agent (Standalone Deployment Package)

[中文文档](README_zh.md)

This folder contains the Agent program that needs to run on **each server being inspected**.

## How It Works

The Agent runs a lightweight HTTP service locally on the server. It collects information such as disk usage via local PowerShell/df commands,
and responds to HTTP queries from the local inspection client.

## Project Structure

```
server/
├── agent.py              # HTTP service entry point (no modification needed)
├── services/             # Inspection service extension directory
│   ├── __init__.py
│   ├── disk.py           # Disk collection (implemented)
│   ├── cpu.py            # CPU collection (implemented)
│   ├── memory.py         # Memory collection (implemented)
│   └── iis.py            # IIS collection (extension example, enable manually)
├── requirements.txt      # Zero third-party dependencies
└── README.md             # This file
```

## Deployment Requirements

**Supported platforms:** Windows / Linux

**Option 1: Run Python directly (recommended for development/testing)**
- Python 3.7+ (for Windows, download and install from the official website; Linux usually includes it)
- Zero third-party dependencies; pure standard library implementation

**Option 2: Package as an executable (recommended for production)**
- If the target server **does not have a Python environment**, use PyInstaller to package it
- Windows is packaged as an exe, Linux as an ELF
- See `scripts/README.md` in the project root for details

## Deployment Steps

### Windows

#### Option A: Run Python Directly

1. Copy this folder to the target server (via RDP paste, shared folder, or FTP).
2. Open Command Prompt or PowerShell, enter this folder, and run:
   ```cmd
   python agent.py --port 5000
   ```

#### Option B: Run the Packaged Executable

See the "Packaging and Deployment" section below.

---

### Linux

#### Option A: Run Python Directly

1. Copy this folder to the target server (via SCP, SFTP, or rsync):
   ```bash
   ssh user@192.168.1.30 "mkdir -p /opt/inspection-agent"
   scp -r server/* user@192.168.1.30:/opt/inspection-agent/
   ```
2. Run the Agent:
   ```bash
   cd /opt/inspection-agent
   python3 agent.py --port 5000
   ```

#### Option B: systemd Background Service (Recommended)

1. Copy files to `/opt/inspection-agent/`.
2. Create the systemd service file `/etc/systemd/system/inspection-agent.service`:
   ```ini
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
   ```
3. Start and enable it to run on boot:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now inspection-agent
   sudo systemctl status inspection-agent
   ```

#### Option C: Package as an ELF Executable

If the target server has an outdated Python version or no Python at all, package it as a standalone ELF:
```bash
bash scripts/build_linux.sh
```
Then copy the entire `server/dist/inspection-agent/` folder to the target server and run it.
See `scripts/README.md` for details.

### Output Language

The Agent's startup/shutdown logs default to Chinese. To output them in English:

```bash
python agent.py --port 5000 --lang en
```

---

### Startup Verification

The Agent listens on `0.0.0.0:5000` by default (the port can be changed via `--port`).
After starting, test locally on the server, regardless of Windows or Linux:

```bash
curl http://localhost:5000/health
```

Or in Windows PowerShell:

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/health"
```

It should return health data in JSON format, for example:
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

> For a lightweight liveness probe, use `GET /ping`, which returns `{"status": "ok"}` without performing any collection.

### Firewall Rule

Make sure the local server firewall allows inbound connections to the Agent port (default 5000).
One-click PowerShell allow rule:

```powershell
New-NetFirewallRule -DisplayName "InspectionAgent" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow
```

## Packaging and Deployment

### Windows Packaging (exe)

Run on the development/packaging machine:

```bash
pip install pyinstaller
python scripts/build_windows.py
```

Copy the entire `server/dist/inspection-agent/` folder to the target server:

```cmd
cd inspection-agent
inspection-agent.exe --port 5000   # Run from command line
start.bat          # Run in foreground
start_hidden.vbs   # Run silently in background (no black window)
```

> **Windows Server 2008 Compatibility Tip**: Use Python 3.7/3.8 for packaging;
> higher versions do not support WS2008. See `scripts/README.md` for details.
>
> **Copy-and-run (no patches required)**: If the target server cannot install the KB3063858/KB2533623 patches, use:
> ```bash
> python scripts/build_windows.py --no-patch-required
> ```
> This mode uses the Python 3.7 embedded runtime for packaging; the resulting exe can run directly on unpatched Win7/2008 R2 systems.

### Linux Packaging (ELF)

```bash
bash scripts/build_linux.sh
```

Copy the entire `server/dist/inspection-agent/` folder to the target server:

```bash
cd inspection-agent
./inspection-agent --port 5000
# or use the helper script
./start.sh --port 5000
```

After packaging, `inspection-agent.service` is automatically generated and can be registered as a systemd service in one step.

---

## Running in the Background on Windows (Optional)

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

**Option D: Executable + start_hidden.vbs**

The packaged folder contains `start_hidden.vbs`; double-click it to run silently in the background.

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

## Linux Support Notes

The Agent fully supports Linux. `services/disk.py` automatically detects the operating system:
- **Windows**: Retrieves information for **all local disks** via PowerShell (automatically includes C:, D:, E:, etc.)
- **Linux**: Collects **all real mount points** via `df -BG` (such as `/`, `/data`, `/home`, etc.), and filters out pseudo filesystems such as `tmpfs`, `devtmpfs`, and `overlay`.
