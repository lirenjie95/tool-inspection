# Server Inspection Scripts (Agent-Client Architecture)

[中文文档](README_zh.md)

A lightweight inspection tool for intranet Windows servers using an **Agent-Client** model,
without requiring complex remote protocols such as SSH/WinRM/WMI.

## Architecture

```
┌─────────────────┐      HTTP (intranet)   ┌─────────────────┐
│  Local Client   │  ──────────────────>   │  Server Agent   │
│  client/main.py │  GET /health /ping     │ server/agent.py │
└─────────────────┘                        └─────────────────┘
       │                                           │
       │ Aggregated output                         │ Local PowerShell/df/free
       ▼                                           ▼
  Inspection report                        CPU / memory / disk data
```

**Advantages:**
- **Zero third-party dependencies** on the server side; pure Python standard library
- No need to open SSH/WinRM; only one HTTP port is required
- Data is collected locally on each server, ensuring accuracy
- **Full support for Windows / Linux** with the same codebase across platforms
- **Built-in CPU / memory / disk collection**, ready to use out of the box
- Add new services by simply creating a new file under `server/services/`

## Project Structure

```
.
├── client/ # Local inspection endpoint (run on one management machine)
│   ├── main.py # Inspection entry point
│   ├── config.json # Server Agent address configuration
│   └── requirements.txt # pip install -r requirements.txt
├── server/ # Server Agent (deploy on each inspected server)
│   ├── agent.py # HTTP service entry point (pure standard library)
│   ├── services/ # Inspection service extension directory
│   │   ├── __init__.py
│   │   ├── disk.py # Disk collection (implemented)
│   │   ├── cpu.py # CPU collection (implemented)
│   │   ├── memory.py # Memory collection (implemented)
│   │   └── iis.py # IIS collection (extension example, enable manually)
│   ├── requirements.txt # Zero dependencies
│   └── README.md # Agent deployment instructions
├── scripts/ # Build scripts
│   ├── build_windows.py # Server Windows exe packaging
│   ├── build_client_windows.py # Client Windows exe packaging
│   ├── build_linux.sh # Linux ELF packaging
│   └── README.md # Packaging instructions
├── tests/ # Unit tests
│   ├── __init__.py
│   ├── test_client.py
│   └── test_server.py
├── .github/
│   └── workflows/
│       └── ci-cd.yml # GitHub Actions CI/CD
└── README.md # This file
```

## Requirements

| Component | Requirement |
|-----------|-------------|
| Python | 3.7+ |
| Server side | No third-party libraries; pure standard library |
| Client side | Only `requests` |
| Network | Intranet connectivity; Agent port accessible |

## Quick Start

### Step 1: Deploy the Agent on Each Server

Choose one of the following methods depending on whether Python is available on the target server.

**Option A: Run Python directly (Python 3.7+ already installed on the server)**

1. Copy the entire `server/` folder to the target server (via RDP paste or shared folder).
2. Start the Agent:
   ```cmd
   cd server
   python agent.py --port 5000
```

**Option B: Package as an executable (recommended for servers without Python)**

By default, this project targets **Windows Server 2008 R2 Enterprise** and requires the build machine to use **Python 3.8.x**.

1. Build on the development machine:
   ```bash
   pip install pyinstaller
   python scripts/build_windows.py
```
2. Copy the entire `server/dist/inspection-agent/` folder to the target server.
3. Run `start.bat` (foreground) or `start_hidden.vbs` (background, silent).

> If the current Python version is higher than 3.8.x, the script will report an error and explain why.
> For Windows Server 2012+ / Win8.1+, use `python scripts/build_windows.py --target modern`.
> **If the target server cannot install system patches (such as KB3063858) but must remain on Win7/2008 R2, use:**
> ```bash
> python scripts/build_windows.py --no-patch-required
> ```
> This mode automatically downloads the Python 3.7 embedded runtime for packaging; the resulting exe can run directly on unpatched legacy systems.
> See `scripts/README.md` for details.

**Firewall rule (required for both options):**

```powershell
New-NetFirewallRule -DisplayName "InspectionAgent" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow
```

> For detailed deployment methods (Windows service, scheduled task, nssm, etc.), please refer to `server/README.md`.

**Agent Endpoints:**

- `GET /health`: Returns full health data (disk, CPU, memory, etc.)
- `GET /ping`: Lightweight liveness probe returning `{"status": "ok"}`

### Step 2: Configure the Client Locally

1. Install dependencies:
   ```bash
   pip install -r client/requirements.txt
```

2. Edit `client/config.json` and fill in the Agent addresses of each server:
   ```json
   {
     "LANGUAGE": "zh",
     "SERVERS": [
       {"role": "app", "ip": "192.168.1.10", "port": 5000, "name": "App Server 01"},
       {"role": "db",  "ip": "192.168.1.20", "port": 5000, "name": "DB Server 01"}
     ],
     "WEBS": [
       {"name": "System Login Page", "url": "http://192.168.1.100/login"}
     ],
     "DISK_THRESHOLD_GB": 30,
     "ROLE_DISK_THRESHOLDS_GB": {
       "db": 30
     }
   }
```

   > Note: `LANGUAGE` defaults to `"zh"` (Chinese). Set it to `"en"` to output reports in English.
   > `DISK_THRESHOLD_GB` is evaluated against the **total free disk space** of a single server. In the example above,
   > the default threshold of 30GB means the sum of free space across all disks on the server must be ≥30GB; the `db` role also requires
   > total free space ≥30GB. To set a higher threshold for the database role, adjust `ROLE_DISK_THRESHOLDS_GB.db`.

### Step 3: Run the Inspection

```bash
cd client
python main.py

# Save a text report
python main.py --output report.txt

# Save a JSON report (for further processing)
python main.py --output report.json

# Use a custom config file (useful for multiple environments: test / production)
# Supports both .json and .py formats
python main.py --config config_prod.json
python main.py --config config_prod.py

# Output in English (overrides config LANGUAGE)
python main.py --lang en
```

### Sample Output

> The example below uses the default disk threshold of 30GB. If `ROLE_DISK_THRESHOLDS_GB` is configured, the corresponding role threshold is used.
> Output is grouped by the `role` field (e.g., `app`, `db`); when no predefined role name is matched, it is displayed as `{role} Server Inspection`.

```
============================================================
Server inspection started
============================================================

[App Server Inspection]
App Server 01 (192.168.1.10) C: 20 GB free D: 20 GB free
  -> Status: OK
  -> CPU: 35%, Memory: 62%
  -> Total disk space check: PASSED

[DB Server Inspection]
DB Server 01 (192.168.1.20) C: 10 GB free D: 15 GB free
  -> Status: OK
  -> CPU: 45%, Memory: 78%
  -> [WARNING] Total disk space below threshold (30GB)

[Web Page Inspection]
System Login Page (http://192.168.1.100/login)
  -> Status: OK (HTTP 200)

============================================================
Inspection Summary
============================================================
1 issue found, please handle:
   - DB Server 01 (192.168.1.20): insufficient total disk space
============================================================
```

### Step 4: Package the Client as a Windows Executable (Optional)

If the management machine does not have Python, you can package the client as a standalone exe:

```bash
pip install pyinstaller
python scripts/build_client_windows.py
```

After packaging, the output is located at `client/dist/inspection-client/` and contains:
- `inspection-client.exe` — Client main program
- `config.json` — Default configuration file (edit directly)
- `start.bat` — Foreground run script
- `start_json.bat` — Run and output a JSON report
- `start_txt.bat` — Run and output a text report

Deployment: copy the entire `client/dist/inspection-client/` folder to the target Windows management machine,
edit `config.json`, and double-click `start.bat` to run.

> CI/CD is also supported: pushing a `v*` tag automatically builds `inspection-client-windows.zip`
> and uploads it to the GitHub Release.

## Extension Guide

### Add a New Server

Simply add the IP and port to the `SERVERS` list in `client/config.json`,
and start `server/agent.py` on the corresponding server.

### Add a New Inspection Service (e.g., IIS, SQL Server)

**Server-side extension:**

1. Create a new file under `server/services/`, for example `sqlserver.py`:
   ```python
   def collect():
       # Implement collection logic
       return {"status": "ok", "databases": [...]}
```

2. Import and register it in `server/agent.py`:
   ```python
   from services.sqlserver import collect as collect_sqlserver
   
   def get_health_data():
       data = {
           "status": "running",
           "os": platform.system(),
           "disks": _safe_collect("disk", collect_disk),
           "cpu": _safe_collect("cpu", collect_cpu),
           "memory": _safe_collect("memory", collect_memory),
       }
       data["sqlserver"] = _safe_collect("sqlserver", collect_sqlserver)
       return data
```

   > `_safe_collect()` isolates exceptions from individual collection services, preventing a single service failure from affecting the entire `/health` endpoint.

**Client-side extension:**

Parse and display the new fields returned by the server in `client/main.py`. Usually two places need to be updated:

1. **Text output**: In the `if data.get("_http_ok")` branch of `inspect_server()`,
   use `lines.append(...)` to add formatted output for the new field.
2. **Structured data**: In `run_inspection()`, write the new field to `structured["servers"][srv["ip"]]["data"]`,
   so that the JSON report generated by `--output report.json` also includes this field.

> **Note:** CPU, memory, and disk are already implemented as built-in services, located at `server/services/cpu.py`,
> `server/services/memory.py`, and `server/services/disk.py` respectively. No additional extension is needed to use them.

### Linux Server Support

The same `server/agent.py` can run directly on Linux. It automatically collects all real mount points (such as `/`, `/data`, `/home`, etc.) via `df -BG`, and filters out pseudo filesystems such as `tmpfs` and `devtmpfs`.

**Deployment:**

```bash
# 1. Copy to the target server
ssh user@192.168.1.30 "mkdir -p /opt/inspection-agent"
scp -r server/* user@192.168.1.30:/opt/inspection-agent/

# 2. Run in the foreground
python3 /opt/inspection-agent/agent.py --port 5000

# 3. Or register as a systemd service
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

**No Python environment? Package as an ELF:**

```bash
bash scripts/build_linux.sh
```

After packaging, an `inspection-agent` ELF executable and a systemd service template are generated.
Like the Windows exe, the target machine does not need Python installed. See `scripts/README.md` for details.

## Testing

The project includes `tests/test_client.py` and `tests/test_server.py`, covering client configuration loading,
server inspection logic, Agent endpoints, and major branches of each collection service.

> Tip: The commands below use `python`; on some systems (such as macOS) you may need to replace it with `python3`.

```bash
# Install test dependencies
python -m pip install pytest coverage
python -m pip install -r client/requirements.txt

# Run all tests
python -m pytest tests/ -v

# View coverage (consistent with CI)
python -m coverage run --branch -m pytest tests/ -v
python -m coverage report --include="server/*,client/*" -m
```

> Tip: The HTTP Handler tests in `tests/test_server.py` start a real HTTP service on a temporary port;
> no manual Agent startup is required.

## Output Language

All command-line tools in this project default to **Chinese** output and can be switched to **English**.

- **Client inspection report**
  - Set `"LANGUAGE": "en"` in `client/config.json`, or
  - Use `python main.py --lang en`

- **Agent startup logs**
  - `python agent.py --port 5000 --lang en`

- **Windows packaging scripts**
  - `python scripts/build_windows.py --lang en`
  - `python scripts/build_client_windows.py --lang en`

- **Linux packaging script**
  - `OUTPUT_LANG=en bash scripts/build_linux.sh`

## Troubleshooting

| Symptom | Troubleshooting Steps |
|---------|----------------------|
| Client connection timeout | Confirm the Agent is running; check whether the server firewall allows the port; confirm intranet connectivity |
| Agent startup error | Confirm Python version >= 3.7; confirm the `services/` folder exists in the current directory |
| Disk data empty | Confirm PowerShell can run normally; confirm local disks exist |
| Web page check failed | Confirm the URL is correct; confirm the local network can access the target web page |
| Startup error `_socket: parameter error` | Legacy systems (Win7/2008 R2) are missing the KB3063858 patch; if the patch cannot be installed, repackage using `--no-patch-required` mode |

## Security Recommendations

- The Agent listens on `0.0.0.0` by default. It is recommended to **use it only in an intranet** and not expose it to the public internet.
- For higher security, place Nginx/iptables in front of the Agent to restrict source IP access.
- For Windows production environments, it is recommended to package the Agent as a Windows Service; for Linux, systemd is recommended.
- Do not hard-code passwords or other sensitive information in scripts; it is recommended to pass them via environment variables.