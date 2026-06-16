# Packaging Scripts

[中文文档](README_zh.md)

## Overview

The packaging scripts convert `server/agent.py` and `client/main.py` along with their dependencies into **Python-free executables**,
so they can run directly on servers or management machines without a Python installation.

> **CI/CD Automated Builds**: This project is configured with GitHub Actions. When a `v*` tag is pushed, it automatically builds and publishes to a GitHub Release:
> - `inspection-agent-linux.tar.gz` (Linux ELF + `start.sh` + `inspection-agent.service`)
> - `inspection-agent-windows.zip` (Windows exe + `start.bat` + `start_hidden.vbs` + `check_prereqs.ps1`)
> - `inspection-client-windows.zip` (Windows client exe + `config.json` + `start.bat` / `start_json.bat` / `start_txt.bat`)
>
> The Windows Agent in CI is packaged using the `--no-patch-required` mode by default,
> so Release packages can run directly on Windows Server 2008 R2 / Win7 systems without the KB3063858/KB2533623 patches.

## Server Windows Packaging

### Environment Setup

```bash
pip install pyinstaller
```

**Compatibility Notes:**

| Target System | Recommended Python | PyInstaller Version | Notes |
|---------------|-------------------|---------------------|-------|
| Windows Server 2008 (non-R2) | 3.7.x | 4.x | Maximum 3.7 support; requires `--target ws2008` |
| Windows Server 2008 R2 | 3.8.x | 5.x | Default target; `--target ws2008r2` |
| Windows Server 2012+ | 3.9+ | 5.x+ | Requires explicit `--target modern` |

> The packaging script defaults to **Windows Server 2008 R2** and validates the Python version automatically.
> If the current Python is 3.9+, the script will report an error and prompt you to switch to Python 3.8.x or use `--target modern`.

### Running the Build

Default build (target Windows Server 2008 R2, requires Python 3.8.x):

```bash
python scripts/build_windows.py
```

To target Windows Server 2012+ / Win8.1+, explicitly specify the modern target:

```bash
python scripts/build_windows.py --target modern
```

### Copy-and-Run Mode (No Patches Required on Legacy Systems)

If your target server is **Windows Server 2008 R2 / Windows 7** and **cannot install system patches**, use the `--no-patch-required` mode:

```bash
python scripts/build_windows.py --no-patch-required
```

This mode automatically performs the following:
1. Downloads the Python 3.7.9 embedded runtime (~7 MB)
2. Downloads PyInstaller 5.13.2 and its dependencies
3. Packages using Python 3.7 + PyInstaller 5.x
4. On first run, files are downloaded from the network (time depends on network speed); subsequent runs reuse the local cache `.py37-legacy-cache/` without re-downloading

**Why does this avoid the patch issue?**

Python 3.8+ uses the `LoadLibraryExW` flags `LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS` when loading C extensions (such as `_socket.pyd`), which requires the target system to have the [KB3063858](https://support.microsoft.com/kb/3063858) patch (or the older KB2533623). Without the patch, you will see:

```
ImportError: DLL load failed while importing _socket: parameter error.
```

Python 3.7 does not use this flag, so the resulting exe can run directly on unpatched legacy systems.

After packaging, the output is located at `server/dist/inspection-agent/` and contains:
- `inspection-agent.exe` — Main program
- `start.bat` — Foreground run script
- `start_hidden.vbs` — Background silent run script (no black window)
- `check_prereqs.ps1` — Pre-deployment system compatibility check script
- Various dependency DLLs

> Note: The local default packaging target is `ws2008r2` (requires Python 3.8.x), while CI Release packages use `--no-patch-required`.
> To also generate a package locally that is compatible with unpatched legacy systems, explicitly add `--no-patch-required`.

### Deployment

Copy the entire `server/dist/inspection-agent/` folder to the target Windows server,
then run `start.bat` or `start_hidden.vbs`.

It is recommended to run `check_prereqs.ps1` once on the target server before deployment to quickly check the patch status.

---

## Client Windows Packaging

### Environment Setup

```bash
pip install pyinstaller
pip install -r client/requirements.txt
```

### Running the Build

```bash
python scripts/build_client_windows.py
```

After packaging, the output is located at `client/dist/inspection-client/` and contains:
- `inspection-client.exe` — Client main program
- `config.json` — Default configuration file (edit directly)
- `start.bat` — Foreground run script
- `start_json.bat` — Run and output a JSON report
- `start_txt.bat` — Run and output a text report
- Various dependency DLLs

### Deployment

Copy the entire `client/dist/inspection-client/` folder to the target Windows management machine,
edit `config.json` to fill in the server Agent addresses, and double-click `start.bat` to run.

---

## Linux Packaging

### Environment Setup

```bash
pip install pyinstaller
```

### Running the Build

```bash
bash scripts/build_linux.sh
```

After packaging, the output is located at `server/dist/inspection-agent/` and contains:
- `inspection-agent` — ELF executable (similar to a Windows exe)
- `start.sh` — Startup script
- `inspection-agent.service` — systemd service template
- Various dependency so libraries

### Deployment

**Option 1: Foreground Run**
```bash
cd inspection-agent
./start.sh --port 5000
```

**Option 2: systemd Background Service (Recommended)**
```bash
sudo cp inspection-agent/inspection-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now inspection-agent
sudo systemctl status inspection-agent
```

### Compatibility Notes

Linux executables packaged by PyInstaller depend on the glibc version used at build time.
It is recommended to build on a system that is the same age as or older than the target system to ensure compatibility.

For example:
- Target machine is CentOS 7 → recommend building on CentOS 7 or a compatible environment
- Target machine is Ubuntu 20.04 → recommend building on Ubuntu 20.04

---

## FAQ

**Q: The packaged program fails to run, reporting missing DLL/so files?**
A: The `--onedir` mode already includes all dependencies. Make sure you copied the **entire folder**, not just a single exe file.

**Q: It reports `ImportError: DLL load failed while importing _socket: parameter error` at runtime?**
A: This is the typical symptom of Windows Server 2008 R2 / Win7 missing the [KB3063858](https://support.microsoft.com/kb/3063858) patch.
   If allowed, install the patch on the target server and restart.
   If **the patch cannot be installed**, repackage using the `--no-patch-required` mode:
   ```bash
   python scripts/build_windows.py --no-patch-required
   ```

**Q: On Windows Server 2008 it reports not supported / missing api-ms-win-core-path-l1-1-0.dll?**
A: Check the Python version used for packaging. WS2008 non-R2 supports up to Python 3.7, and WS2008 R2 supports up to Python 3.8.
   The packaging script defaults to WS2008 R2; if the current Python is 3.9+, it will report an error and prompt you to switch versions.
   You can also explicitly specify the target: `--target ws2008r2` (default), `--target ws2008`, or `--target modern`.
   If the patch cannot be installed and you must deploy to a legacy system, use `--no-patch-required`.

**Q: Can it be packaged as a single file (--onefile)?**
A: Yes, but `--onedir` mode starts faster and has better compatibility, especially for legacy systems. If you need a single file,
   change `--onedir` to `--onefile` in the script.
