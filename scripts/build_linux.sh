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
#     server/dist/inspection-agent/  (文件夹，根目录仅保留 ELF / start.sh)
#     server/dist/inspection-agent/  (directory; root keeps only ELF / start.sh)

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
# --onedir 模式，依赖文件统一放在 _internal/ 子目录
# Package
# --onedir mode, dependencies go to _internal/ subdirectory
python3 -m PyInstaller \
    --name inspection-agent \
    --onedir \
    --console \
    agent.py

DIST_DIR="$SERVER_DIR/dist/inspection-agent"

# 复制 server 目录的中英文 README 到输出目录
# Copy the server READMEs to the output directory
cp "$SERVER_DIR/README.md" "$DIST_DIR/README.md"
cp "$SERVER_DIR/README_zh.md" "$DIST_DIR/README_zh.md"

# 创建启动脚本
# Create startup script
cat > "$DIST_DIR/start.sh" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
./inspection-agent "$@"
EOF
chmod +x "$DIST_DIR/start.sh"

# 创建 systemd service 文件模板，放入 scripts/ 子目录，保持根目录简洁
# Create systemd service file template under scripts/ to keep the root clean
mkdir -p "$DIST_DIR/scripts"
cat > "$DIST_DIR/scripts/inspection-agent.service" << 'EOF'
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
msg "       sudo cp scripts/inspection-agent.service /etc/systemd/system/" "       sudo cp scripts/inspection-agent.service /etc/systemd/system/"
msg "       sudo systemctl daemon-reload" "       sudo systemctl daemon-reload"
msg "       sudo systemctl enable --now inspection-agent" "       sudo systemctl enable --now inspection-agent"
msg "========================================" "========================================"
