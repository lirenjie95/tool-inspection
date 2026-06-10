#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 打包脚本

将 server/agent.py 及其 services/ 打包为独立可执行程序，
用于在没有 Python 环境的 Windows 服务器上运行。

环境要求:
    - Python 3.7 或 3.8 (Windows Server 2008/2008R2 最高支持 3.8)
    - pip install pyinstaller

用法:
    python scripts/build_windows.py

输出:
    server/dist/inspection-agent/  (文件夹，包含 exe 和依赖)
"""

import subprocess
import sys
import os
import shutil


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
    server_dir = os.path.join(root, "server")

    print("=" * 60)
    print("开始打包 Inspection Agent (Windows)")
    print("=" * 60)

    if not check_pyinstaller():
        print("错误: 未安装 PyInstaller")
        print("请先执行: pip install pyinstaller")
        sys.exit(1)

    # 清理旧构建
    for name in ["build", "dist"]:
        path = os.path.join(server_dir, name)
        if os.path.exists(path):
            shutil.rmtree(path)
            print(f"已清理: {path}")
    for name in ["*.spec"]:
        import glob
        for p in glob.glob(os.path.join(server_dir, name)):
            os.remove(p)
            print(f"已清理: {p}")

    # 执行打包
    # --onedir 模式比 --onefile 兼容性更好，适合 Windows Server 2008
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "inspection-agent",
        "--onedir",          # 单目录模式，稳定性更好
        "--console",         # 控制台程序
        "--workpath", os.path.join(server_dir, "build"),
        "--distpath", os.path.join(server_dir, "dist"),
        "--specpath", server_dir,
        os.path.join(server_dir, "agent.py"),
    ]

    print(f"执行命令: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("\n错误: 打包失败")
        sys.exit(1)

    # 创建启动脚本
    dist_dir = os.path.join(server_dir, "dist", "inspection-agent")
    bat_path = os.path.join(dist_dir, "start.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write("cd /d \"%~dp0\"\n")
        f.write("inspection-agent.exe --port 5000\n")
        f.write("pause\n")

    # 创建后台运行脚本
    vbs_path = os.path.join(dist_dir, "start_hidden.vbs")
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write('Set WshShell = CreateObject("WScript.Shell")\n')
        f.write('WshShell.Run "inspection-agent.exe --port 5000", 0, False\n')
        f.write('Set WshShell = Nothing\n')

    print("\n" + "=" * 60)
    print("打包成功!")
    print(f"输出目录: {dist_dir}")
    print("\n部署方式:")
    print("1. 将上述文件夹整体复制到目标服务器")
    print("2. 运行方式:")
    print("   - 前台运行: 双击 start.bat")
    print("   - 后台运行: 双击 start_hidden.vbs")
    print("   - 命令行:   inspection-agent.exe --port 5000")
    print("=" * 60)


if __name__ == "__main__":
    main()
