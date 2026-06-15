#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Windows 打包脚本

将 server/agent.py 及其 services/ 打包为独立可执行程序，
用于在没有 Python 环境的 Windows 服务器上运行。

默认目标平台：Windows Server 2008 R2 Enterprise
因此默认要求打包环境为 Python 3.8.x，防止生成不兼容的 exe。

环境要求:
    - Python 3.8.x（默认目标 Windows Server 2008 R2）
    - Python 3.7.x（如需兼容 Windows Server 2008 非 R2，使用 --target ws2008）
    - Python 3.9+（仅当目标为 Server 2012+/Win8.1+ 时使用 --target modern）
    - pip install pyinstaller

用法:
    python scripts/build_windows.py
    python scripts/build_windows.py --target modern

输出:
    server/dist/inspection-agent/  (文件夹，包含 exe 和依赖)
"""

import argparse
import subprocess
import sys
import os
import shutil


# 目标系统与最高支持的 Python 版本
TARGET_COMPATIBILITY = {
    "ws2008": (3, 7),      # Windows Server 2008（非 R2）
    "ws2008r2": (3, 8),    # Windows Server 2008 R2（默认目标）
    "modern": None,        # Server 2012+ / Win8.1+，无限制
}


def check_pyinstaller():
    """检查 PyInstaller 是否已安装"""
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        return False


def check_python_compatibility(target):
    """检查当前 Python 版本是否满足目标系统的兼容性要求"""
    major, minor = sys.version_info[:2]
    max_version = TARGET_COMPATIBILITY.get(target)

    if max_version is None:
        # modern 目标不做强制限制，但友好提示老系统兼容性问题
        if (major, minor) >= (3, 9):
            print("\n[提示] 当前使用 Python {}.{} 打包".format(major, minor))
            print("       Python 3.9+ 生成的 exe 不支持 Windows Server 2008/2008 R2 / Windows 7。")
            print("       若目标服务器为老系统，请使用 Python 3.8.x 并去掉 --target modern。")
        return

    # 老系统目标：强制校验 Python 主/次版本
    if (major, minor) > max_version:
        print("\n[错误] 目标系统 '{}' 要求 Python <= {}.{}, 但当前为 Python {}.{}".format(
            target, max_version[0], max_version[1], major, minor))
        print("       请安装兼容的 Python 版本后重新打包：")
        if target == "ws2008r2":
            print("       Windows Server 2008 R2 请使用 Python 3.8.x")
        elif target == "ws2008":
            print("       Windows Server 2008（非 R2）请使用 Python 3.7.x")
        print("       如目标为 Server 2012+ / Win8.1+，可改用 --target modern")
        sys.exit(1)

    print("\n[信息] 兼容性检查通过：Python {}.{} 可用于目标 '{}'".format(
        major, minor, target))


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="将 server/agent.py 打包为 Windows 可执行程序"
    )
    parser.add_argument(
        "--target",
        choices=list(TARGET_COMPATIBILITY.keys()),
        default="ws2008r2",
        help=(
            "目标 Windows 版本（默认 ws2008r2）。"
            "指定老系统时会强制检查 Python 版本，避免生成在目标机上无法运行的 exe。"
        ),
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # 切换到项目根目录
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)
    server_dir = os.path.join(root, "server")

    print("=" * 60)
    print("开始打包 Inspection Agent (Windows)")
    print("目标平台: {}".format(args.target))
    print("=" * 60)

    if not check_pyinstaller():
        print("错误: 未安装 PyInstaller")
        print("请先执行: pip install pyinstaller")
        sys.exit(1)

    check_python_compatibility(args.target)

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
