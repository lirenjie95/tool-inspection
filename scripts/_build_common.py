#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 打包公共辅助模块 / Common helpers for Windows packaging scripts.

此模块抽取 server 与 client Windows 打包脚本中共享的兼容性检查、
Python 3.7 嵌入式运行时准备等逻辑，避免重复代码。

This module extracts logic shared between the server and client Windows
packaging scripts, such as compatibility checks and Python 3.7 embedded
runtime preparation, to avoid duplication.
"""

import glob
import os
import shutil
import subprocess
import sys
import zipfile

import urllib.request
import urllib.error


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


def check_python_compatibility(target, no_patch_required, t):
    """检查当前 Python 版本是否满足目标系统的兼容性要求。

    Check whether the current Python version meets the target system's
    compatibility requirements.  ``t`` is the caller's translation function.
    """
    major, minor = sys.version_info[:2]
    max_version = TARGET_COMPATIBILITY.get(target)

    if no_patch_required:
        print(t("no_patch_required_mode"))
        print(t("no_patch_required_note"))
        return

    if max_version is None:
        # modern 目标不做强制限制，但友好提示老系统兼容性问题
        # No hard limit for the modern target, but warn about compatibility
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

    print(t("compat_check_passed").format(major, minor, target))


def download_file(url, dest, t, description=None):
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


def download_wheels(cache_dir, t):
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


def setup_py37_runtime(cache_dir, t):
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
            download_file(PY37_EMBED_URL, zip_path, t, PY37_EMBED_ZIP)

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
        download_file(PY37_GET_PIP_URL, get_pip_path, t, "get-pip.py")

    # 3. 下载依赖 wheel
    # 3. Download dependency wheels
    if not os.path.exists(wheels_dir) or not glob.glob(os.path.join(wheels_dir, "pyinstaller-*.whl")):
        download_wheels(cache_dir, t)

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
