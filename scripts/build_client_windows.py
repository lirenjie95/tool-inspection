#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 客户端打包脚本

将 client/main.py 及其依赖打包为独立可执行程序，
用于在没有 Python 环境的 Windows 管理机上直接运行巡检。

Packaging script for the Windows client.
Packages client/main.py and its dependencies into a standalone executable
for running inspections directly on Windows management machines without Python.

环境要求 / Requirements:
    - Python 3.7+
    - pip install pyinstaller

用法 / Usage:
    python scripts/build_client_windows.py

输出 / Output:
    client/dist/inspection-client/  (文件夹，包含 exe 和依赖)
    client/dist/inspection-client/  (directory containing the exe and dependencies)
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys


# 默认输出语言 / Default output language
DEFAULT_LANG = "zh"

# 当前运行语言，由命令行参数设置 / Current runtime language, set by command-line argument
_CURRENT_LANG = DEFAULT_LANG

# 翻译表 / Translation table
TRANSLATIONS = {
    "zh": {
        "argparse_description": "将 client/main.py 打包为 Windows 可执行程序",
        "lang_help": "输出语言 (默认: zh)",
        "start_packaging": "开始打包 Inspection Client (Windows)",
        "pyinstaller_not_installed": "错误: 未安装 PyInstaller",
        "please_install_pyinstaller": "请先执行: pip install pyinstaller",
        "cleaned": "已清理: {path}",
        "executing_command": "执行命令: {cmd}",
        "packaging_failed": "\n错误: 打包失败",
        "copied_default_config": "已复制默认配置文件: {path}",
        "packaging_successful": "打包成功!",
        "output_directory": "输出目录: {dist_dir}",
        "deployment_instructions": "部署方式:",
        "step1_copy_folder": "1. 将上述文件夹整体复制到目标 Windows 管理机",
        "step2_edit_config": "2. 编辑 config.json，填入实际服务器 Agent 地址",
        "step3_run_methods": "3. 运行方式:",
        "run_foreground": "   - 前台运行: 双击 start.bat",
        "run_json_output": "   - 输出 JSON 报告: 双击 start_json.bat",
        "run_txt_output": "   - 输出文本报告: 双击 start_txt.bat",
        "run_command_line": "   - 命令行: inspection-client.exe --config config_prod.py",
    },
    "en": {
        "argparse_description": "Package client/main.py as a Windows executable",
        "lang_help": "Output language (default: zh)",
        "start_packaging": "Start packaging Inspection Client (Windows)",
        "pyinstaller_not_installed": "Error: PyInstaller is not installed",
        "please_install_pyinstaller": "Please run: pip install pyinstaller",
        "cleaned": "Cleaned: {path}",
        "executing_command": "Executing command: {cmd}",
        "packaging_failed": "\nError: Packaging failed",
        "copied_default_config": "Copied default config file: {path}",
        "packaging_successful": "Packaging successful!",
        "output_directory": "Output directory: {dist_dir}",
        "deployment_instructions": "Deployment instructions:",
        "step1_copy_folder": "1. Copy the entire folder to the target Windows management machine",
        "step2_edit_config": "2. Edit config.json with actual server Agent addresses",
        "step3_run_methods": "3. How to run:",
        "run_foreground": "   - Foreground: double-click start.bat",
        "run_json_output": "   - Output JSON report: double-click start_json.bat",
        "run_txt_output": "   - Output text report: double-click start_txt.bat",
        "run_command_line": "   - Command line: inspection-client.exe --config config_prod.py",
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


def check_pyinstaller():
    """检查 PyInstaller 是否已安装。

    Check whether PyInstaller is installed.
    """
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        return False


def parse_args():
    """解析命令行参数。

    Parse command-line arguments.
    """
    # 先解析 --lang，使 argparse 帮助信息使用正确语言 / Parse --lang first so argparse help text uses the correct language
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
        "--lang",
        type=str,
        default=DEFAULT_LANG,
        choices=["zh", "en"],
        help=t("lang_help"),
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # 切换到项目根目录 / Switch to the project root directory
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)
    client_dir = os.path.join(root, "client")

    print("=" * 60)
    print(t("start_packaging"))
    print("=" * 60)

    if not check_pyinstaller():
        print(t("pyinstaller_not_installed"))
        print(t("please_install_pyinstaller"))
        sys.exit(1)

    # 清理旧构建 / Clean up old builds
    for name in ["build", "dist"]:
        path = os.path.join(client_dir, name)
        if os.path.exists(path):
            shutil.rmtree(path)
            print(t("cleaned", path=path))
    for p in glob.glob(os.path.join(client_dir, "*.spec")):
        os.remove(p)
        print(t("cleaned", path=p))

    # 打包 / Package
    # --onedir 模式兼容性更好，避免单文件解压问题 / --onedir mode has better compatibility and avoids single-file extraction issues
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "inspection-client",
        "--onedir",
        "--console",
        "--workpath", os.path.join(client_dir, "build"),
        "--distpath", os.path.join(client_dir, "dist"),
        "--specpath", client_dir,
        os.path.join(client_dir, "main.py"),
    ]

    print(t("executing_command", cmd=' '.join(cmd)))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(t("packaging_failed"))
        sys.exit(1)

    dist_dir = os.path.join(client_dir, "dist", "inspection-client")

    # 复制默认配置文件到输出目录，方便用户直接修改 / Copy the default config file to the output directory for easy user modification
    shutil.copy2(
        os.path.join(client_dir, "config.json"),
        os.path.join(dist_dir, "config.json"),
    )
    print(t("copied_default_config", path=f"{dist_dir}/config.json"))

    # 创建启动脚本 / Create startup script
    bat_path = os.path.join(dist_dir, "start.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write("cd /d \"%~dp0\"\n")
        f.write("inspection-client.exe\n")
        f.write("pause\n")

    # 创建输出 JSON 报告的快捷脚本 / Create shortcut script for JSON report output
    json_bat_path = os.path.join(dist_dir, "start_json.bat")
    with open(json_bat_path, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write("cd /d \"%~dp0\"\n")
        f.write("inspection-client.exe --output report.json\n")
        f.write("pause\n")

    # 创建输出文本报告的快捷脚本 / Create shortcut script for text report output
    txt_bat_path = os.path.join(dist_dir, "start_txt.bat")
    with open(txt_bat_path, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write("cd /d \"%~dp0\"\n")
        f.write("inspection-client.exe --output report.txt\n")
        f.write("pause\n")

    print("\n" + "=" * 60)
    print(t("packaging_successful"))
    print(t("output_directory", dist_dir=dist_dir))
    print(t("deployment_instructions"))
    print(t("step1_copy_folder"))
    print(t("step2_edit_config"))
    print(t("step3_run_methods"))
    print(t("run_foreground"))
    print(t("run_json_output"))
    print(t("run_txt_output"))
    print(t("run_command_line"))
    print("=" * 60)


if __name__ == "__main__":
    main()
