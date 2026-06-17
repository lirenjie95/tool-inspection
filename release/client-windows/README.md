# Inspection Client (Windows)

[中文文档](README_zh.md)

This package contains the standalone Windows executable for the local inspection client. It queries each server's Agent and aggregates the inspection report.

## Contents

- `inspection-client.exe` — Client executable
- `config.json` — Server / web page configuration (edit this before running)
- `start.bat` — Run and print the text report
- `start_json.bat` — Run and save `report.json`
- `start_txt.bat` — Run and save `report.txt`
- `_internal/` — Runtime dependencies
- `README.md` / `README_zh.md` — This documentation

## Quick Start

1. Copy the entire `inspection-client` folder to your Windows management machine.
2. Edit `config.json` and fill in the Agent addresses of the servers you want to inspect:
   ```json
   {
     "LANGUAGE": "en",
     "SERVERS": [
       {"role": "app", "ip": "192.168.1.10", "port": 5000, "name": "App Server 01"},
       {"role": "db",  "ip": "192.168.1.20", "port": 5000, "name": "DB Server 01"}
     ],
     "WEBS": [
       {"name": "Login Page", "url": "http://192.168.1.100/login"}
     ],
     "DISK_THRESHOLD_GB": 30
   }
   ```
3. Double-click `start.bat` to run the inspection.

## Output Modes

- `start.bat` — Print the report to the console window
- `start_json.bat` — Save the structured report to `report.json`
- `start_txt.bat` — Save the human-readable report to `report.txt`

## Output Language

Set `"LANGUAGE": "en"` for English or `"LANGUAGE": "zh"` for Chinese in `config.json`.

## Compatibility

- This CI Release package is built with `--no-patch-required`, so it can run directly on Windows Server 2008 R2 / Windows 7 systems without the KB3063858/KB2533623 patches.
- The client itself can also be run directly from Python source without packaging; see the project repository for details.
