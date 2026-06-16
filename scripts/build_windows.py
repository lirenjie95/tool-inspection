#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 打包脚本

将 server/agent.py 及其 services/ 打包为独立可执行程序，
用于在没有 Python 环境的 Windows 服务器上运行。

Packaging script for Windows.
Packages server/agent.py and its services/ into a standalone executable
for running on Windows servers without a Python environment.

默认目标平台：Windows Server 2008 R2 Enterprise
因此默认要求打包环境为 Python 3.8.x，防止生成不兼容的 exe。

Default target platform: Windows Server 2008 R2 Enterprise.
Therefore the default packaging environment is Python 3.8.x to avoid generating incompatible executables.

环境要求 / Requirements:
    - Python 3.8.x（默认目标 Windows Server 2008 R2）
      Python 3.8.x (default target Windows Server 2008 R2)
    - Python 3.7.x（如需兼容 Windows Server 2008 非 R2，使用 --target ws2008）
      Python 3.7.x (for Windows Server 2008 non-R2 compatibility, use --target ws2008)
    - Python 3.9+（仅当目标为 Server 2012+/Win8.1+ 时使用 --target modern）
      Python 3.9+ (only when targeting Server 2012+/Win8.1+, use --target modern)
    - pip install pyinstaller

用法 / Usage:
    python scripts/build_windows.py
    python scripts/build_windows.py --target modern
    python scripts/build_windows.py --no-patch-required   # 复制到未打补丁的老系统也能用
                                                          # Also works when copied to older unpatched systems

输出 / Output:
    server/dist/inspection-agent/  (文件夹，包含 exe 和依赖)
    server/dist/inspection-agent/  (directory containing the exe and dependencies)
"""

import argparse
import subprocess
import sys
import os
import shutil
import glob
import zipfile
import urllib.request
import urllib.error


# 默认输出语言 / Default output language
DEFAULT_LANG = "zh"

# 当前运行语言，由命令行参数设置 / Current runtime language, set by command-line argument
_CURRENT_LANG = DEFAULT_LANG

# 翻译表 / Translation table
TRANSLATIONS = {
    "zh": {
        "argparse_description": "将 server/agent.py 打包为 Windows 可执行程序",
        "target_help": (
            "目标 Windows 版本（默认 ws2008r2）。"
            "指定老系统时会强制检查 Python 版本，避免生成在目标机上无法运行的 exe。"
        ),
        "no_patch_required_help": (
            "生成可在未安装 KB3063858/KB2533623 补丁的 Windows Server 2008 R2 / Win7 "
            "上直接运行的 exe。此模式会自动下载并使用 Python 3.7 嵌入式运行时 + PyInstaller 5.x。"
        ),
        "lang_help": "输出语言 (默认: zh)",
        "no_patch_required_mode": "\n[信息] 启用 --no-patch-required 模式，将使用 Python 3.7 嵌入式运行时打包",
        "no_patch_required_note": "       生成的 exe 可在未安装 KB3063858/KB2533623 补丁的 Win7/2008 R2 上运行",
        "current_python": "\n[提示] 当前使用 Python {}.{}",
        "python39_compat_warning": "       Python 3.9+ 生成的 exe 不支持 Windows Server 2008/2008 R2 / Windows 7。",
        "use_older_python_warning": "       若目标服务器为老系统，请使用 Python 3.8.x 并去掉 --target modern。",
        "python_version_error": "\n[错误] 目标系统 '{}' 要求 Python <= {}.{}, 但当前为 Python {}.{}",
        "install_compatible_python": "       请安装兼容的 Python 版本后重新打包：",
        "ws2008r2_python_requirement": "       Windows Server 2008 R2 请使用 Python 3.8.x",
        "ws2008_python_requirement": "       Windows Server 2008（非 R2）请使用 Python 3.7.x",
        "use_target_modern_tip": "       如目标为 Server 2012+ / Win8.1+，可改用 --target modern",
        "use_no_patch_tip": "       如无法安装补丁且必须部署到老系统，可使用 --no-patch-required",
        "compat_check_passed": "\n[信息] 兼容性检查通过：Python {}.{} 可用于目标 '{}'",
        "downloading": "下载 {desc} ...",
        "download_error": "错误: 下载失败 {url}\n       {error}",
        "saved": "已保存: {dest}",
        "download_py37_deps": "\n[信息] 使用当前 Python 下载 Python 3.7 可用的 PyInstaller 依赖包...",
        "download_deps_failed": "\n错误: 下载依赖包失败，请检查网络连接",
        "extracting": "解压 {filename} ...",
        "installing_pip": "\n[信息] 在 Python 3.7 嵌入式运行时中安装 pip...",
        "pip_install_failed": "错误: pip 安装失败",
        "pyinstaller_exists": "\n[信息] Python 3.7 运行时中已存在 PyInstaller，跳过安装",
        "installing_pyinstaller": "\n[信息] 在 Python 3.7 运行时中安装 PyInstaller...",
        "pyinstaller_install_failed": "错误: PyInstaller 安装失败",
        "executing_command": "\n执行命令: {cmd}",
        "packaging_failed": "\n错误: 打包失败",
        "cleaned": "已清理: {path}",
        "start_packaging": "开始打包 Inspection Agent (Windows)",
        "target_platform": "目标平台: {target}",
        "pyinstaller_not_installed": "错误: 未安装 PyInstaller",
        "please_install_pyinstaller": "请先执行: pip install pyinstaller",
        "packaging_successful": "打包成功!",
        "output_directory": "输出目录: {dist_dir}",
        "deployment_instructions": "部署方式:",
        "step1_copy_folder": "1. 将上述文件夹整体复制到目标服务器",
        "step2_compat_check": "2. (推荐) 先在目标服务器运行一次兼容性检查:",
        "step2_run_powershell": "   - 右键点击 check_prereqs.ps1 → 使用 PowerShell 运行",
        "step3_run_methods": "3. 运行方式:",
        "run_foreground": "   - 前台运行: 双击 start.bat",
        "run_background": "   - 后台运行: 双击 start_hidden.vbs",
        "run_command_line": "   - 命令行:   inspection-agent.exe --port 5000",
        "no_patch_required_build_note": "\n[提示] 本次使用 --no-patch-required 模式打包",
        "no_patch_required_build_note2": "       生成的 exe 适用于未安装 KB3063858/KB2533623 补丁的老系统",
    },
    "en": {
        "argparse_description": "Package server/agent.py as a Windows executable",
        "target_help": (
            "Target Windows version (default ws2008r2). "
            "When targeting older systems, Python version is enforced to avoid producing incompatible executables."
        ),
        "no_patch_required_help": (
            "Generate an exe that can run directly on Windows Server 2008 R2 / Win7 "
            "without KB3063858/KB2533623 patches. This mode automatically downloads and uses Python 3.7 embedded runtime + PyInstaller 5.x."
        ),
        "lang_help": "Output language (default: zh)",
        "no_patch_required_mode": "\n[INFO] --no-patch-required mode enabled, packaging with Python 3.7 embedded runtime",
        "no_patch_required_note": "       Generated exe can run on Win7/2008 R2 without KB3063858/KB2533623 patches",
        "current_python": "\n[NOTE] Currently using Python {}.{}",
        "python39_compat_warning": "       Python 3.9+ executables do not support Windows Server 2008/2008 R2 / Windows 7.",
        "use_older_python_warning": "       If target servers are older systems, use Python 3.8.x and omit --target modern.",
        "python_version_error": "\n[ERROR] Target system '{}' requires Python <= {}.{}, but current is Python {}.{}",
        "install_compatible_python": "       Please install a compatible Python version and repackage:",
        "ws2008r2_python_requirement": "       For Windows Server 2008 R2 use Python 3.8.x",
        "ws2008_python_requirement": "       For Windows Server 2008 (non-R2) use Python 3.7.x",
        "use_target_modern_tip": "       For Server 2012+ / Win8.1+ targets, use --target modern",
        "use_no_patch_tip": "       If patches cannot be installed and you must deploy to old systems, use --no-patch-required",
        "compat_check_passed": "\n[INFO] Compatibility check passed: Python {}.{} can be used for target '{}'",
        "downloading": "Downloading {desc} ...",
        "download_error": "Error: download failed {url}\n       {error}",
        "saved": "Saved: {dest}",
        "download_py37_deps": "\n[INFO] Using current Python to download PyInstaller dependencies compatible with Python 3.7...",
        "download_deps_failed": "\nError: Failed to download dependencies, please check network connection",
        "extracting": "Extracting {filename} ...",
        "installing_pip": "\n[INFO] Installing pip in Python 3.7 embedded runtime...",
        "pip_install_failed": "Error: pip installation failed",
        "pyinstaller_exists": "\n[INFO] PyInstaller already exists in Python 3.7 runtime, skipping installation",
        "installing_pyinstaller": "\n[INFO] Installing PyInstaller in Python 3.7 runtime...",
        "pyinstaller_install_failed": "Error: PyInstaller installation failed",
        "executing_command": "\nExecuting command: {cmd}",
        "packaging_failed": "\nError: Packaging failed",
        "cleaned": "Cleaned: {path}",
        "start_packaging": "Start packaging Inspection Agent (Windows)",
        "target_platform": "Target platform: {target}",
        "pyinstaller_not_installed": "Error: PyInstaller is not installed",
        "please_install_pyinstaller": "Please run: pip install pyinstaller",
        "packaging_successful": "Packaging successful!",
        "output_directory": "Output directory: {dist_dir}",
        "deployment_instructions": "Deployment instructions:",
        "step1_copy_folder": "1. Copy the entire folder to the target server",
        "step2_compat_check": "2. (Recommended) Run a compatibility check on the target server first:",
        "step2_run_powershell": "   - Right-click check_prereqs.ps1 → Run with PowerShell",
        "step3_run_methods": "3. How to run:",
        "run_foreground": "   - Foreground: double-click start.bat",
        "run_background": "   - Background: double-click start_hidden.vbs",
        "run_command_line": "   - Command line: inspection-agent.exe --port 5000",
        "no_patch_required_build_note": "\n[NOTE] This build used --no-patch-required mode",
        "no_patch_required_build_note2": "       Generated exe is suitable for old systems without KB3063858/KB2533623 patches",
    },
}


def t(key: str, lang: str = None, **kwargs) -> str:
    """获取指定语言的翻译文本 / Get translated text for the specified language."""
    if lang is None:
        lang = _CURRENT_LANG
    text = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANG]).get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text


# 目标系统与最高支持的 Python 版本
# Target systems and the maximum supported Python version
TARGET_COMPATIBILITY = {
    "ws2008": (3, 7),      # Windows Server 2008（非 R2）
    "ws2008r2": (3, 8),    # Windows Server 2008 R2（默认目标）
    "modern": None,        # Server 2012+ / Win8.1+，无限制
}

# Python 3.7 嵌入式运行时配置（用于 --no-patch-required 模式）
# Python 3.7 embedded runtime configuration (for --no-patch-required mode)
PY37_VERSION = "3.7.9"
PY37_EMBED_ZIP = "python-3.7.9-embed-amd64.zip"
PY37_EMBED_URL = f"https://www.python.org/ftp/python/{PY37_VERSION}/{PY37_EMBED_ZIP}"
PY37_GET_PIP_URL = "https://bootstrap.pypa.io/pip/3.7/get-pip.py"
PY37_PYINSTALLER = "5.13.2"
PY37_PIP = "23.3.2"
PY37_SETUPTOOLS = "68.0.0"
PY37_WHEEL = "0.42.0"


def check_pyinstaller():
    """检查 PyInstaller 是否已安装。

    Check whether PyInstaller is installed.
    """
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        return False


def check_python_compatibility(target, no_patch_required):
    """检查当前 Python 版本是否满足目标系统的兼容性要求。

    Check whether the current Python version meets the target system's compatibility requirements.
    """
    major, minor = sys.version_info[:2]
    max_version = TARGET_COMPATIBILITY.get(target)

    if no_patch_required:
        # 使用 Python 3.7 打包时，最高支持到 Windows Server 2008 R2
        # When packaging with Python 3.7, the maximum supported target is Windows Server 2008 R2
        print(t("no_patch_required_mode"))
        print(t("no_patch_required_note"))
        return

    if max_version is None:
        # modern 目标不做强制限制，但友好提示老系统兼容性问题
        # No hard limit for the modern target, but warn about compatibility with older systems
        if (major, minor) >= (3, 9):
            print(t("current_python").format(major, minor))
            print(t("python39_compat_warning"))
            print(t("use_older_python_warning"))
        return

    # 老系统目标：强制校验 Python 主/次版本
    # Older system targets: enforce Python major/minor version validation
    if (major, minor) > max_version:
        print(t("python_version_error").format(
            target, max_version[0], max_version[1], major, minor))
        print(t("install_compatible_python"))
        if target == "ws2008r2":
            print(t("ws2008r2_python_requirement"))
        elif target == "ws2008":
            print(t("ws2008_python_requirement"))
        print(t("use_target_modern_tip"))
        print(t("use_no_patch_tip"))
        sys.exit(1)

    print(t("compat_check_passed").format(
        major, minor, target))


def download_file(url, dest, description=None):
    """使用当前 Python 下载文件，显示进度。

    Download a file using the current Python interpreter, showing progress.
    """
    desc = description or os.path.basename(dest)
    print(t("downloading", desc=desc))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        urllib.request.urlretrieve(url, dest)
    except urllib.error.URLError as e:
        print(t("download_error", url=url, error=e))
        sys.exit(1)
    print(t("saved", dest=dest))


def download_wheels(cache_dir):
    """下载 PyInstaller 5.x 及其依赖的 wheel 到缓存目录。

    Download PyInstaller 5.x and its dependency wheels to the cache directory.
    """
    wheels_dir = os.path.join(cache_dir, "wheels")
    os.makedirs(wheels_dir, exist_ok=True)

    packages = [
        f"pip=={PY37_PIP}",
        f"setuptools=={PY37_SETUPTOOLS}",
        f"wheel=={PY37_WHEEL}",
        f"pyinstaller=={PY37_PYINSTALLER}",
        "altgraph",
        "pefile",
        "pywin32-ctypes",
        "pyinstaller-hooks-contrib",
        "packaging",
        "importlib-metadata",
        "zipp",
        "typing_extensions",
    ]

    print(t("download_py37_deps"))
    cmd = [
        sys.executable, "-m", "pip", "download",
        "--dest", wheels_dir,
        "--python-version", "3.7",
        "--platform", "win_amd64",
        "--only-binary=:all:",
    ] + packages

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(t("download_deps_failed"))
        sys.exit(1)

    return wheels_dir


def setup_py37_runtime(cache_dir):
    """准备 Python 3.7 嵌入式运行时，并安装 PyInstaller。

    Prepare the Python 3.7 embedded runtime and install PyInstaller.
    """
    py37_dir = os.path.join(cache_dir, "py37")
    python_exe = os.path.join(py37_dir, "python.exe")
    get_pip_path = os.path.join(cache_dir, "get-pip.py")
    wheels_dir = os.path.join(cache_dir, "wheels")
    pth_file = os.path.join(py37_dir, "python37._pth")

    # 1. 下载并解压 Python 3.7 嵌入式运行时
    # 1. Download and extract the Python 3.7 embedded runtime
    if not os.path.exists(python_exe):
        zip_path = os.path.join(cache_dir, PY37_EMBED_ZIP)
        if not os.path.exists(zip_path):
            download_file(PY37_EMBED_URL, zip_path, PY37_EMBED_ZIP)

        print(t("extracting", filename=PY37_EMBED_ZIP))
        if os.path.exists(py37_dir):
            shutil.rmtree(py37_dir)
        os.makedirs(py37_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(py37_dir)

        # 启用 site-packages 支持
        # Enable site-packages support
        if os.path.exists(pth_file):
            with open(pth_file, "r", encoding="utf-8") as f:
                content = f.read()
            content = content.replace("#import site", "import site")
            with open(pth_file, "w", encoding="utf-8") as f:
                f.write(content)

    # 2. 下载 get-pip.py
    # 2. Download get-pip.py
    if not os.path.exists(get_pip_path):
        download_file(PY37_GET_PIP_URL, get_pip_path, "get-pip.py")

    # 3. 下载依赖 wheel
    # 3. Download dependency wheels
    if not os.path.exists(wheels_dir) or not glob.glob(os.path.join(wheels_dir, "pyinstaller-*.whl")):
        download_wheels(cache_dir)

    # 4. 安装 pip（如果尚未安装）
    # 4. Install pip (if not already installed)
    try:
        subprocess.run([python_exe, "-m", "pip", "--version"], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        print(t("installing_pip"))
        result = subprocess.run([
            python_exe, get_pip_path,
            "--no-index", "--find-links", wheels_dir,
            "--no-warn-script-location",
        ])
        if result.returncode != 0:
            print(t("pip_install_failed"))
            sys.exit(1)

    # 5. 安装 PyInstaller
    # 5. Install PyInstaller
    try:
        subprocess.run([python_exe, "-m", "PyInstaller", "--version"], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(t("pyinstaller_exists"))
    except subprocess.CalledProcessError:
        print(t("installing_pyinstaller"))
        result = subprocess.run([
            python_exe, "-m", "pip", "install",
            "--no-index", "--find-links", wheels_dir,
            f"pyinstaller=={PY37_PYINSTALLER}",
        ])
        if result.returncode != 0:
            print(t("pyinstaller_install_failed"))
            sys.exit(1)

    return python_exe


def parse_args():
    """解析命令行参数。

    Parse command-line arguments.
    """
    # 先解析 --lang，使 argparse 帮助信息使用正确语言
    # Parse --lang first so argparse help text uses the correct language
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument(
        "--lang",
        type=str,
        default=DEFAULT_LANG,
        choices=["zh", "en"],
    )
    pre_args, _ = pre_parser.parse_known_args()
    global _CURRENT_LANG
    _CURRENT_LANG = pre_args.lang

    parser = argparse.ArgumentParser(
        description=t("argparse_description")
    )
    parser.add_argument(
        "--target",
        choices=list(TARGET_COMPATIBILITY.keys()),
        default="ws2008r2",
        help=t("target_help"),
    )
    parser.add_argument(
        "--no-patch-required",
        action="store_true",
        dest="no_patch_required",
        help=t("no_patch_required_help"),
    )
    parser.add_argument(
        "--lang",
        type=str,
        default=DEFAULT_LANG,
        choices=["zh", "en"],
        help=t("lang_help"),
    )
    return parser.parse_args()


def build_agent(server_dir, python_exe, name="inspection-agent"):
    """调用 PyInstaller 执行打包。

    Invoke PyInstaller to perform packaging.
    """
    cmd = [
        python_exe, "-m", "PyInstaller",
        "--name", name,
        "--onedir",          # 单目录模式，稳定性更好 / Single-directory mode, more stable
        "--console",         # 控制台程序 / Console application
        "--noupx",           # 禁用 UPX，防止 DLL 损坏导致运行时参数错误 / Disable UPX to avoid DLL corruption causing runtime parameter errors
        "--workpath", os.path.join(server_dir, "build"),
        "--distpath", os.path.join(server_dir, "dist"),
        "--specpath", server_dir,
        os.path.join(server_dir, "agent.py"),
    ]

    print(t("executing_command", cmd=' '.join(cmd)))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(t("packaging_failed"))
        sys.exit(1)


def create_auxiliary_scripts(dist_dir):
    """创建启动脚本、后台运行脚本和兼容性检查脚本。

    Create startup, background-run, and compatibility-check scripts.
    """
    # 启动脚本
    # Startup script
    bat_path = os.path.join(dist_dir, "start.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write("cd /d \"%~dp0\"\n")
        f.write("inspection-agent.exe --port 5000\n")
        f.write("pause\n")

    # 后台运行脚本
    # Background-run script
    vbs_path = os.path.join(dist_dir, "start_hidden.vbs")
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write('Set WshShell = CreateObject("WScript.Shell")\n')
        f.write('WshShell.Run "inspection-agent.exe --port 5000", 0, False\n')
        f.write('Set WshShell = Nothing\n')

    # 部署前系统兼容性检查脚本
    # Pre-deployment system compatibility check script
    ps_path = os.path.join(dist_dir, "check_prereqs.ps1")
    with open(ps_path, "w", encoding="utf-8") as f:
        f.write('# 检查 Inspection Agent 运行环境\n')
        f.write('$os = Get-WmiObject Win32_OperatingSystem\n')
        f.write('Write-Host "操作系统: $($os.Caption) $($os.OSArchitecture)"\n')
        f.write('Write-Host "版本号: $($os.Version)"\n')
        f.write('\n')
        f.write('# Windows Server 2008 R2 / Win7 需要 KB3063858(或 KB2533623) 补丁\n')
        f.write('$required = "KB3063858"\n')
        f.write('$hotfix = Get-HotFix -Id $required -ErrorAction SilentlyContinue\n')
        f.write('if ($hotfix) {\n')
        f.write('    Write-Host "补丁检查: 已通过 ($($hotfix.InstalledOn))" -ForegroundColor Green\n')
        f.write('} else {\n')
        f.write('    Write-Host "补丁检查: 未安装 $required" -ForegroundColor Red\n')
        f.write('    Write-Host "说明: 老系统缺少该补丁会导致 _socket DLL 加载失败（参数错误）" -ForegroundColor Red\n')
        f.write('    Write-Host "下载地址(请按系统架构选择):" -ForegroundColor Yellow\n')
        f.write('    Write-Host "  Win7/2008 R2 x64: https://download.microsoft.com/download/0/8/E/08E0386B-F6AF-4651-8D1B-C0A95D2731F0/Windows6.1-KB3063858-x64.msu"\n')
        f.write('    Write-Host "  Win7/2008 R2 x86: https://download.microsoft.com/download/C/9/6/C96CD606-3E05-4E1C-B201-51211AE80B1E/Windows6.1-KB3063858-x86.msu"\n')
        f.write('}\n')
        f.write('\n')
        f.write('pause\n')


def clean_build(server_dir):
    """清理旧构建产物。

    Clean up old build artifacts.
    """
    for name in ["build", "dist"]:
        path = os.path.join(server_dir, name)
        if os.path.exists(path):
            shutil.rmtree(path)
            print(t("cleaned", path=path))
    for p in glob.glob(os.path.join(server_dir, "*.spec")):
        os.remove(p)
        print(t("cleaned", path=p))


def main():
    args = parse_args()

    # 切换到项目根目录
    # Switch to the project root directory
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)
    server_dir = os.path.join(root, "server")

    print("=" * 60)
    print(t("start_packaging"))
    print(t("target_platform", target=args.target))
    print("=" * 60)

    check_python_compatibility(args.target, args.no_patch_required)

    if args.no_patch_required:
        cache_dir = os.path.join(root, ".py37-legacy-cache")
        python_exe = setup_py37_runtime(cache_dir)
    else:
        if not check_pyinstaller():
            print(t("pyinstaller_not_installed"))
            print(t("please_install_pyinstaller"))
            sys.exit(1)
        python_exe = sys.executable

    clean_build(server_dir)
    build_agent(server_dir, python_exe)

    dist_dir = os.path.join(server_dir, "dist", "inspection-agent")
    create_auxiliary_scripts(dist_dir)

    print("\n" + "=" * 60)
    print(t("packaging_successful"))
    print(t("output_directory", dist_dir=dist_dir))
    print(t("deployment_instructions"))
    print(t("step1_copy_folder"))
    print(t("step2_compat_check"))
    print(t("step2_run_powershell"))
    print(t("step3_run_methods"))
    print(t("run_foreground"))
    print(t("run_background"))
    print(t("run_command_line"))
    if args.no_patch_required:
        print(t("no_patch_required_build_note"))
        print(t("no_patch_required_build_note2"))
    print("=" * 60)


if __name__ == "__main__":
    main()
