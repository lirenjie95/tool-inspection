#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 客户端打包脚本

将 client/main.py 及其依赖打包为独立可执行程序，
用于在没有 Python 环境的 Windows 管理机上直接运行巡检。

环境要求:
    - Python 3.7+
    - pip install pyinstaller

用法:
    python scripts/build_client_windows.py

输出:
    client/dist/inspection-client/  (文件夹，包含 exe 和依赖)
"""

import glob
import os
import shutil
import subprocess
import sys


def check_pyinstaller():
    """检查 PyInstaller 是否已安装"""
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        return False


def main():
    # 切换到项目根目录
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)
    client_dir = os.path.join(root, "client")

    print("=" * 60)
    print("开始打包 Inspection Client (Windows)")
    print("=" * 60)

    if not check_pyinstaller():
        print("错误: 未安装 PyInstaller")
        print("请先执行: pip install pyinstaller")
        sys.exit(1)

    # 清理旧构建
    for name in ["build", "dist"]:
        path = os.path.join(client_dir, name)
        if os.path.exists(path):
            shutil.rmtree(path)
            print(f"已清理: {path}")
    for p in glob.glob(os.path.join(client_dir, "*.spec")):
        os.remove(p)
        print(f"已清理: {p}")

    # 打包
    # --onedir 模式兼容性更好，避免单文件解压问题
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

    print(f"执行命令: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("\n错误: 打包失败")
        sys.exit(1)

    dist_dir = os.path.join(client_dir, "dist", "inspection-client")

    # 复制默认配置文件到输出目录，方便用户直接修改
    shutil.copy2(
        os.path.join(client_dir, "config.json"),
        os.path.join(dist_dir, "config.json"),
    )
    print(f"已复制默认配置文件: {dist_dir}/config.json")

    # 创建启动脚本
    bat_path = os.path.join(dist_dir, "start.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write("cd /d \"%~dp0\"\n")
        f.write("inspection-client.exe\n")
        f.write("pause\n")

    # 创建输出 JSON 报告的快捷脚本
    json_bat_path = os.path.join(dist_dir, "start_json.bat")
    with open(json_bat_path, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write("cd /d \"%~dp0\"\n")
        f.write("inspection-client.exe --output report.json\n")
        f.write("pause\n")

    # 创建输出文本报告的快捷脚本
    txt_bat_path = os.path.join(dist_dir, "start_txt.bat")
    with open(txt_bat_path, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write("cd /d \"%~dp0\"\n")
        f.write("inspection-client.exe --output report.txt\n")
        f.write("pause\n")

    print("\n" + "=" * 60)
    print("打包成功!")
    print(f"输出目录: {dist_dir}")
    print("\n部署方式:")
    print("1. 将上述文件夹整体复制到目标 Windows 管理机")
    print("2. 编辑 config.json，填入实际服务器 Agent 地址")
    print("3. 运行方式:")
    print("   - 前台运行: 双击 start.bat")
    print("   - 输出 JSON 报告: 双击 start_json.bat")
    print("   - 输出文本报告: 双击 start_txt.bat")
    print("   - 命令行: inspection-client.exe --config config_prod.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
