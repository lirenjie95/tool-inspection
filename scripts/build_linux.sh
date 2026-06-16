#!/bin/bash
# -*- coding: utf-8 -*-
# Linux 打包脚本
# Linux packaging script
#
# 将 server/agent.py 打包为 ELF 可执行文件，
# 效果类似 Windows 上的 exe，可直接在 Linux 服务器上运行。
#
# Package server/agent.py as an ELF executable,
# similar to an exe on Windows, so it can run directly on Linux servers.
#
# 环境要求 / Requirements:
#     - Python 3.7+
#     - pip install pyinstaller
#
# 用法 / Usage:
#     bash scripts/build_linux.sh
#
# 输出 / Output:
#     server/dist/inspection-agent/  (文件夹，包含 ELF 可执行文件和依赖)
#     server/dist/inspection-agent/  (directory containing the ELF executable and dependencies)

set -e

# 输出语言，通过环境变量 OUTPUT_LANG 设置（zh 或 en，默认 zh）
# Output language, set via OUTPUT_LANG environment variable (zh or en, default zh)
OUTPUT_LANG="${OUTPUT_LANG:-zh}"

# 根据 OUTPUT_LANG 输出中文或英文消息
# Print Chinese or English message based on OUTPUT_LANG
msg() {
    if [ "$OUTPUT_LANG" = "en" ]; then
        echo "$2"
    else
        echo "$1"
    fi
}

ROOT="$(cd "$(dirname "$0")/.." && pwd)"  # 项目根目录 / Project root directory
SERVER_DIR="$ROOT/server"                 # 服务端目录 / Server directory

msg "========================================" "========================================"
msg "开始打包 Inspection Agent (Linux)" "Start packaging Inspection Agent (Linux)"
msg "========================================" "========================================"

# 检查 pyinstaller
# Check pyinstaller
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    msg "错误: 未安装 PyInstaller" "Error: PyInstaller is not installed"
    msg "请先执行: pip install pyinstaller" "Please run: pip install pyinstaller"
    exit 1
fi

# 清理旧构建
# Clean up old builds
cd "$SERVER_DIR"
rm -rf build dist *.spec

# 打包
# --onedir 模式兼容性最好，避免单文件解压问题
# Package
# --onedir mode has the best compatibility and avoids single-file extraction issues
python3 -m PyInstaller \
    --name inspection-agent \
    --onedir \
    --console \
    agent.py

DIST_DIR="$SERVER_DIR/dist/inspection-agent"

# 创建启动脚本
# Create startup script
cat > "$DIST_DIR/start.sh" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
./inspection-agent "$@"
EOF
chmod +x "$DIST_DIR/start.sh"

# 创建 systemd service 文件模板
# 默认使用 /opt/inspection-agent 作为部署路径，可根据实际情况修改
# Create systemd service file template
# Defaults to /opt/inspection-agent as the deployment path; modify as needed
cat > "$DIST_DIR/inspection-agent.service" << 'EOF'
[Unit]
Description=Inspection Agent
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/inspection-agent
ExecStart=/opt/inspection-agent/inspection-agent --port 5000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

msg "========================================" "========================================"
msg "打包成功!" "Packaging successful!"
msg "输出目录: $DIST_DIR" "Output directory: $DIST_DIR"
msg "" ""
msg "部署方式:" "Deployment instructions:"
msg "1. 将上述文件夹整体复制到目标服务器" "1. Copy the entire folder to the target server"
msg "2. 运行方式:" "2. How to run:"
msg "   - 前台运行: ./start.sh --port 5000" "   - Foreground: ./start.sh --port 5000"
msg "   - 后台运行(systemd):" "   - Background (systemd):"
msg "       sudo cp inspection-agent.service /etc/systemd/system/" "       sudo cp inspection-agent.service /etc/systemd/system/"
msg "       sudo systemctl daemon-reload" "       sudo systemctl daemon-reload"
msg "       sudo systemctl enable --now inspection-agent" "       sudo systemctl enable --now inspection-agent"
msg "========================================" "========================================"
