# Inspection Client

[中文文档](README_zh.md)

This folder contains the local inspection client. It queries each server's Agent via HTTP and aggregates the inspection report.

For the overall architecture and deployment guide, see the [project root README](../README.md).

## Files

- `main.py` — Client entry point
- `config.json` — Server / web page configuration (edit this before running)
- `requirements.txt` — Python dependencies (`requests`)

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Edit `config.json` and fill in your server Agent addresses.
3. Run the inspection:
   ```bash
   python main.py
   ```

## CLI Options

See the "Step 3: Run the Inspection" section in the [root README](../README.md) for all supported options, including `--output`, `--config`, and `--lang`.

## Windows Executable Packaging

If the management machine does not have Python, package the client as a standalone executable. See `../scripts/README.md` for packaging instructions.
