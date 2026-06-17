# Server Inspection Agent (Linux)

[中文文档](README_linux_zh.md)

This is the Agent program that runs on **each Linux server being inspected**. It exposes a lightweight HTTP interface for the local inspection client to query.

> **Source vs. Packaged:** This README describes both running from the `server/` source folder and running a packaged executable. When using a CI release package, the root contains the `inspection-agent` ELF executable, helper script `start.sh`, systemd service template, and runtime dependencies under `_internal/`.

## Files

- `agent.py` — HTTP service entry point (no modification needed)
- `services/` — Inspection service extension directory
- `requirements.txt` — Zero third-party dependencies
- `README.md` / `README_zh.md` — This guide

## Part 1: Use the Packaged Release

Download `inspection-agent-linux.tar.gz` from GitHub Releases and extract it on the target server.

Steps:

1. Extract the package:

   ```bash
   tar -xzf inspection-agent-linux.tar.gz -C /opt/
   cd /opt/inspection-agent
   ```

2. Start the Agent:

   ```bash
   ./inspection-agent --port 5000
   # or use the helper script
   ./start.sh --port 5000
   ```

3. Or register as a systemd background service:

   ```bash
   sudo cp scripts/inspection-agent.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now inspection-agent
   sudo systemctl status inspection-agent
   ```

> **Compatibility Tip**: PyInstaller-packaged Linux executables depend on the glibc version used at build time. Build on a system that is the same age as or older than the target system to ensure compatibility. See `../scripts/README.md` for details.

## Part 2: Run from Python Source

### Requirements

- Python 3.7+ installed on the target server
- Zero third-party dependencies; pure standard library implementation

### Steps

1. Copy the `server/` folder to the target server:

   ```bash
   ssh user@192.168.1.30 "mkdir -p /opt/inspection-agent"
   scp -r server/* user@192.168.1.30:/opt/inspection-agent/
   ```

2. Run in the foreground:

   ```bash
   cd /opt/inspection-agent
   python3 agent.py --port 5000
   ```

3. Or register as a systemd background service manually:

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

## Output Language

The Agent's startup/shutdown logs default to Chinese. To output them in English:

```bash
python3 agent.py --port 5000 --lang en
```

## Startup Verification

The Agent listens on `0.0.0.0:5000` by default (the port can be changed via `--port`). After starting, test locally on the server:

```bash
curl http://localhost:5000/health
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

## Firewall Rule

Make sure the local server firewall allows inbound connections to the Agent port (default 5000). For example, on systems using `firewalld`:

```bash
sudo firewall-cmd --add-port=5000/tcp --permanent
sudo firewall-cmd --reload
```

Or on systems using `ufw`:

```bash
sudo ufw allow 5000/tcp
```

## Packaging from Source (Optional)

If you need to build the Linux package yourself, run on the packaging machine:

```bash
pip install pyinstaller
bash scripts/build_linux.sh
```

Then copy the entire `server/dist/inspection-agent/` folder to the target server. See `../scripts/README.md` for details.

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

To add new inspection items (such as Nginx, MySQL, event logs, etc.; CPU, memory, and disk are already built-in), follow these steps:

1. **Create a service file**

   Create a new file under `services/`, for example `services/mysql.py`:

   ```python
   def collect():
       # Implement collection logic
       return {"status": "ok", "databases": [...]}
   ```

2. **Register with the Agent**

   Import at the top of `agent.py`:

   ```python
   from services.mysql import collect as collect_mysql
   ```

   Add to `get_health_data()`:

   ```python
   data["mysql"] = _safe_collect("mysql", collect_mysql)
   ```

   The existing built-in services (disk / cpu / memory) are also called via `_safe_collect`; new services should follow the same pattern.

   > `_safe_collect()` isolates exceptions from individual collection services, preventing a single service failure from rendering the entire `/health` endpoint unavailable.

3. **Display on the client**

   Parse and display the new `mysql` field in `client/main.py`.

## Linux Support Notes

The Agent fully supports Linux. `services/disk.py` automatically detects the operating system and collects **all real mount points** via `df -BG` (such as `/`, `/data`, `/home`, etc.), filtering out pseudo filesystems such as `tmpfs`, `devtmpfs`, and `overlay`.
