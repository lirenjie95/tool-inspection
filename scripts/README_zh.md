# 打包脚本说明

## 概述

打包脚本用于将 `server/agent.py` 和 `client/main.py` 及其依赖转换为**不依赖 Python 环境**的可执行程序，
方便在没有安装 Python 的服务器或管理机上直接运行。

> **CI/CD 自动构建**：本项目配置了 GitHub Actions，在推送 `v*` 标签时会自动构建并发布到 GitHub Release：
> - `inspection-agent-linux.tar.gz`（Linux ELF + `start.sh` + `inspection-agent.service`）
> - `inspection-agent-windows.zip`（Windows exe + `start.bat` + `start_hidden.vbs` + `check_prereqs.ps1`）
> - `inspection-client-windows.zip`（Windows 客户端 exe + `config.json` + `start.bat` / `start_json.bat` / `start_txt.bat`）
>
> 其中 Windows Agent 与 Windows 客户端在 CI 中均默认使用 `--no-patch-required` 模式打包，
> 因此 Release 包可在未安装 KB3063858/KB2533623 补丁的 Windows Server 2008 R2 / Win7 上直接运行。

## 服务器 Windows 打包

### 环境准备

```bash
pip install pyinstaller
```

**兼容性提示：**

| 目标系统 | 建议 Python 版本 | PyInstaller 版本 | 说明 |
|---------|----------------|-----------------|------|
| Windows Server 2008 (非 R2) | 3.7.x | 4.x | 最高只支持 3.7，需 `--target ws2008` |
| Windows Server 2008 R2 | 3.8.x | 5.x | 默认目标，`--target ws2008r2` |
| Windows Server 2012+ | 3.9+ | 5.x+ | 需显式指定 `--target modern` |

> 打包脚本默认目标为 **Windows Server 2008 R2**，会自动校验 Python 版本。
> 如果当前 Python 为 3.9+，脚本会报错并提示换用 Python 3.8.x 或 `--target modern`。

### 执行打包

默认打包（目标 Windows Server 2008 R2，要求 Python 3.8.x）：

```bash
python scripts/build_windows.py
```

如需面向 Windows Server 2012+ / Win8.1+ 打包，可显式指定 modern 目标：

```bash
python scripts/build_windows.py --target modern
```

### 复制即用模式（老系统无需安装补丁）

如果你的目标服务器是 **Windows Server 2008 R2 / Windows 7**，且**无法安装系统补丁**，请使用 `--no-patch-required` 模式：

```bash
python scripts/build_windows.py --no-patch-required
```

该模式会自动完成以下操作：
1. 下载 Python 3.7.9 嵌入式运行时（约 7 MB）
2. 下载 PyInstaller 5.13.2 及其依赖
3. 使用 Python 3.7 + PyInstaller 5.x 打包
4. 首次执行会从网络下载，耗时取决于网络；后续复用本地缓存 `.py37-legacy-cache/`，不再重复下载

**为什么这样做可以避免补丁问题？**

Python 3.8+ 在加载 C 扩展（如 `_socket.pyd`）时使用了 `LoadLibraryExW` 的 `LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS` 标志，这需要目标系统安装 [KB3063858](https://support.microsoft.com/kb/3063858)（或旧版 KB2533623）补丁。缺少补丁时会出现：

```
ImportError: DLL load failed while importing _socket: 参数错误。
```

Python 3.7 不使用该标志，因此生成的 exe 可以在未打补丁的老系统上直接运行。

打包完成后，输出位于 `server/dist/inspection-agent/`，包含：
- `inspection-agent.exe` — 主程序
- `start.bat` — 前台运行脚本
- `start_hidden.vbs` — 后台静默运行脚本（无黑窗口）
- `check_prereqs.ps1` — 部署前系统兼容性检查脚本
- 各种依赖 DLL

> 注意：本地默认打包目标为 `ws2008r2`（要求 Python 3.8.x），而 CI 中的 Release 包使用 `--no-patch-required`。
> 如需本地也生成兼容未打补丁老系统的包，请显式加上 `--no-patch-required`。

### 部署

将 `server/dist/inspection-agent/` **整个文件夹**复制到目标 Windows 服务器，
然后运行 `start.bat` 或 `start_hidden.vbs`。

部署前建议在目标服务器运行一次 `check_prereqs.ps1`，快速检查补丁状态。

---

## 客户端 Windows 打包

### 环境准备

```bash
pip install pyinstaller
pip install -r client/requirements.txt
```

**兼容性提示：**

| 目标系统 | 建议 Python 版本 | PyInstaller 版本 | 说明 |
|---------|----------------|-----------------|------|
| Windows Server 2008 (非 R2) | 3.7.x | 4.x | 最高只支持 3.7，需 `--target ws2008` |
| Windows Server 2008 R2 / Windows 7 | 3.8.x | 5.x | 默认目标，`--target ws2008r2` |
| Windows Server 2012+ / Win8.1+ | 3.9+ | 5.x+ | 需显式指定 `--target modern` |

> 打包脚本默认目标为 **Windows Server 2008 R2 / Windows 7**，会自动校验 Python 版本。
> 如果当前 Python 为 3.9+，脚本会报错并提示换用 Python 3.8.x 或 `--target modern`。

### 执行打包

默认打包（目标 Windows Server 2008 R2 / Windows 7，要求 Python 3.8.x）：

```bash
python scripts/build_client_windows.py
```

如需面向 Windows Server 2012+ / Win8.1+ 打包，可显式指定 modern 目标：

```bash
python scripts/build_client_windows.py --target modern
```

### 复制即用模式（老系统无需安装补丁）

如果你的目标管理机是 **Windows Server 2008 R2 / Windows 7**，且**无法安装系统补丁**，请使用 `--no-patch-required` 模式：

```bash
python scripts/build_client_windows.py --no-patch-required
```

该模式复用服务端打包的 Python 3.7 嵌入式运行时（详见[服务器 Windows 打包](#服务器-windows-打包)），
因此生成的客户端 exe 可在未打补丁的老系统上直接运行。

打包完成后，输出位于 `client/dist/inspection-client/`，包含：
- `inspection-client.exe` — 客户端主程序
- `config.json` — 默认配置文件（可直接修改）
- `start.bat` — 前台运行脚本
- `start_json.bat` — 运行并输出 JSON 报告
- `start_txt.bat` — 运行并输出文本报告
- 各种依赖 DLL

### 部署

将 `client/dist/inspection-client/` **整个文件夹**复制到目标 Windows 管理机，
编辑 `config.json` 填入服务器 Agent 地址后，双击 `start.bat` 即可运行。

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

**Q: 运行时报 `ImportError: DLL load failed while importing _socket: 参数错误`？**
A: 这是 Windows Server 2008 R2 / Win7 缺少 [KB3063858](https://support.microsoft.com/kb/3063858) 补丁的典型表现。
   如果允许，在目标机器安装该补丁后重启即可。
   如果**无法安装补丁**，请使用 `--no-patch-required` 模式重新打包：
   ```bash
   # 服务器 Agent
   python scripts/build_windows.py --no-patch-required
   # 本地客户端
   python scripts/build_client_windows.py --no-patch-required
   ```

**Q: Windows Server 2008 上提示不支持 / 缺少 api-ms-win-core-path-l1-1-0.dll？**
A: 请检查打包时使用的 Python 版本。WS2008 非 R2 最高支持 Python 3.7，WS2008 R2 最高支持 3.8。
   打包脚本默认以 WS2008 R2 为目标，若当前 Python 为 3.9+ 会直接报错并提示切换版本。
   也可显式指定目标：`--target ws2008r2`（默认）、`--target ws2008`、`--target modern`。
   如无法安装补丁且必须部署到老系统，请使用 `--no-patch-required`。

## 输出语言

所有打包脚本默认输出中文，同时支持英文。

- **服务器 Windows 打包**：`python scripts/build_windows.py --lang en`
- **客户端 Windows 打包**：`python scripts/build_client_windows.py --lang en`
- **Linux 打包**：`OUTPUT_LANG=en bash scripts/build_linux.sh`

**Q: 能否打包成单文件（--onefile）？**
A: 可以，但 `--onedir` 模式启动更快、兼容性更好，尤其适合老系统。如需单文件，
   修改脚本中的 `--onedir` 为 `--onefile` 即可。
