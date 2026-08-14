# Inspection Client

[中文文档](README_zh.md)

This folder contains the local inspection client. It queries each server's Agent via HTTP and aggregates the inspection report.

> **Source vs. Packaged:** This README describes both running from the `client/` source folder and running a packaged executable. When using a CI release package, the root contains a single-file `inspection-client.exe` (all dependencies bundled), `config.json`, and helper `start*.bat` scripts.

## Quickstart

> Prerequisite: the Agent is already running on each target server (see `../server/README_windows.md` / `../server/README_linux.md`).

1. Extract `inspection-client-windows.zip` on the management machine.
2. Edit `config.json` and fill in your servers (minimal example):

   ```json
   {
     "SERVERS": [
       {"role": "app", "ip": "192.168.1.10", "port": 5000, "name": "App Server 01"}
     ],
     "WEBS": [],
     "DISK_THRESHOLD_GB": 30
   }
   ```

3. Double-click `start.bat` — the inspection report prints to the console. Use `start_json.bat` / `start_txt.bat` to save the report to a file.

For all command-line options and output formats, see the full guide below.

## Files

- `main.py` — Client entry point
- `config.json` — Server / web page configuration (edit this before running)
- `requirements.txt` — Python dependencies (`requests`)

## Part 1: Use the Packaged Release

Download the release package (for example `inspection-client-windows.zip` from GitHub Releases) and extract it. The package root contains:

- `inspection-client.exe` — single-file executable with all runtime dependencies bundled
- `config.json`
- `start.bat` — foreground run with default text output
- `start_json.bat` — save JSON report to `report.json`
- `start_txt.bat` — save text report to `report.txt`

> **Windows 7 / Server 2008 R2 release compatibility:**
> - `v0.3.0` — **not usable** on Win7/2008 R2 (built with Python 3.11; fails with missing `api-ms-win-core-path-l1-1-0.dll`)
> - `v0.3.1` / `v0.3.2` — usable (multi-file package built on the Python 3.7 runtime)
> - `v0.3.3+` — usable (single-file exe built on the Python 3.7 runtime)
>
> If the single-file exe of `v0.3.3+` fails to start on your Win7 machine, download
> [`v0.3.2`](https://github.com/lirenjie95/tool-inspection/releases/tag/v0.3.2) instead — its multi-file
> package is the most compatible with legacy systems.

Steps:

1. Edit `config.json` and fill in your server Agent addresses.
2. Run one of the helper scripts, or run from the command line:

   ```cmd
   start.bat
   start_json.bat
   start_txt.bat
   inspection-client.exe --config config_prod.json
   ```

For all supported options, see [Step 3: Run the Inspection](../README.md#step-3-run-the-inspection) in the root README.

## Part 2: Run from Python Source

### Requirements

- Python 3.7+
- `pip install -r requirements.txt`

### Steps

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Edit `config.json` and fill in your server Agent addresses.
3. Run the inspection:

   ```bash
   python main.py
   ```

For all supported options, including `--output`, `--config`, and `--lang`, see [Step 3: Run the Inspection](../README.md#step-3-run-the-inspection) in the root README.

## Build Your Own Package (Optional)

If the management machine does not have Python, package the client as a standalone executable. See `../scripts/README.md` for packaging instructions.
