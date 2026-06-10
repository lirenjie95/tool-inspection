# 打包脚本说明

## 概述

打包脚本用于将 `server/agent.py` 及其依赖转换为**不依赖 Python 环境**的可执行程序，
方便在没有安装 Python 的服务器上直接运行。

## Windows 打包

### 环境准备

```bash
pip install pyinstaller
```

**兼容性提示：**

| 目标系统 | 建议 Python 版本 | PyInstaller 版本 | 说明 |
|---------|----------------|-----------------|------|
| Windows Server 2008 (非 R2) | 3.7.x | 4.x | 最高只支持 3.7 |
| Windows Server 2008 R2 | 3.8.x | 5.x | 官方最后支持的版本 |
| Windows Server 2012+ | 3.9+ | 5.x+ | 推荐 |

> 如果目标服务器是 Windows Server 2008，请确保打包用的 Python 版本不超过 3.8，
> 否则可执行文件无法在目标机上运行。

### 执行打包

```bash
python scripts/build_windows.py
```

打包完成后，输出位于 `server/dist/inspection-agent/`，包含：
- `inspection-agent.exe` — 主程序
- `start.bat` — 前台运行脚本
- `start_hidden.vbs` — 后台静默运行脚本（无黑窗口）
- 各种依赖 DLL

### 部署

将 `server/dist/inspection-agent/` **整个文件夹**复制到目标 Windows 服务器，
然后运行 `start.bat` 或 `start_hidden.vbs`。

---

## Linux 打包

### 环境准备

```bash
pip install pyinstaller
```

### 执行打包

```bash
bash scripts/build_linux.sh
```

打包完成后，输出位于 `server/dist/inspection-agent/`，包含：
- `inspection-agent` — ELF 可执行文件（类似 Windows exe）
- `start.sh` — 启动脚本
- `inspection-agent.service` — systemd 服务模板
- 各种依赖 so 库

### 部署

**方式一：前台运行**
```bash
cd inspection-agent
./start.sh --port 5000
```

**方式二：systemd 后台服务（推荐）**
```bash
sudo cp inspection-agent/inspection-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now inspection-agent
sudo systemctl status inspection-agent
```

### 兼容性提示

PyInstaller 打包的 Linux 可执行文件依赖构建时的 glibc 版本，
建议在**目标系统相同或更旧的系统**上打包，以确保兼容性。

例如：
- 目标机是 CentOS 7 → 建议在 CentOS 7 或兼容环境上打包
- 目标机是 Ubuntu 20.04 → 建议在 Ubuntu 20.04 上打包

---

## 常见问题

**Q: 打包后的程序无法运行，提示缺少 DLL/so？**
A: `--onedir` 模式已包含所有依赖，请确保复制的是**整个文件夹**而不是单个 exe 文件。

**Q: Windows Server 2008 上提示不支持？**
A: 请检查打包时使用的 Python 版本。WS2008 非 R2 最高支持 Python 3.7，WS2008 R2 最高支持 3.8。

**Q: 能否打包成单文件（--onefile）？**
A: 可以，但 `--onedir` 模式启动更快、兼容性更好，尤其适合老系统。如需单文件，
   修改脚本中的 `--onedir` 为 `--onefile` 即可。
