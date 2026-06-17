# Inspection Client

[中文文档](README_zh.md)

This folder contains the local inspection client. It queries each server's Agent via HTTP and aggregates the inspection report.

> **Source vs. Packaged:** This README describes both running from the `client/` source folder and running a packaged executable. When using a CI release package, the root contains `inspection-client.exe`, `config.json`, helper `start*.bat` scripts, and runtime dependencies under `_internal/`.

## Files

- `main.py` — Client entry point
- `config.json` — Server / web page configuration (edit this before running)
- `requirements.txt` — Python dependencies (`requests`)

## Part 1: Use the Packaged Release

Download the release package (for example `inspection-client-windows.zip` from GitHub Releases) and extract it. The package root contains:

- `inspection-client.exe`
- `config.json`
- `start.bat` — foreground run with default text output
- `start_json.bat` — save JSON report to `report.json`
- `start_txt.bat` — save text report to `report.txt`
- `_internal/` — runtime dependencies

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
