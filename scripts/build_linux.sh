#!/bin/bash
# -*- coding: utf-8 -*-
# Linux 打包脚本
#
# 将 server/agent.py 打包为 ELF 可执行文件，
# 效果类似 Windows 上的 exe，可直接在 Linux 服务器上运行。
#
# 环境要求:
#     - Python 3.7+
#     - pip install pyinstaller
#
# 用法:
#     bash scripts/build_linux.sh
#
# 输出:
#     server/dist/inspection-agent/  (文件夹，包含 ELF 可执行文件和依赖)

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERVER_DIR="$ROOT/server"

echo "========================================"
echo "开始打包 Inspection Agent (Linux)"
echo "========================================"

# 检查 pyinstaller
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "错误: 未安装 PyInstaller"
    echo "请先执行: pip install pyinstaller"
    exit 1
fi

# 清理旧构建
cd "$SERVER_DIR"
rm -rf build dist *.spec

# 打包
# --onedir 模式兼容性最好，避免单文件解压问题
python3 -m PyInstaller \
    --name inspection-agent \
    --onedir \
    --console \
    agent.py

DIST_DIR="$SERVER_DIR/dist/inspection-agent"

# 创建启动脚本
cat > "$DIST_DIR/start.sh" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
./inspection-agent "$@"
EOF
chmod +x "$DIST_DIR/start.sh"

# 创建 systemd service 文件模板
cat > "$DIST_DIR/inspection-agent.service" << EOF
[Unit]
Description=Inspection Agent
After=network.target

[Service]
Type=simple
WorkingDirectory=$DIST_DIR
ExecStart=$DIST_DIR/inspection-agent --port 5000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "========================================"
echo "打包成功!"
echo "输出目录: $DIST_DIR"
echo ""
echo "部署方式:"
echo "1. 将上述文件夹整体复制到目标服务器"
echo "2. 运行方式:"
echo "   - 前台运行: ./start.sh --port 5000"
echo "   - 后台运行(systemd):"
echo "       sudo cp inspection-agent.service /etc/systemd/system/"
echo "       sudo systemctl daemon-reload"
echo "       sudo systemctl enable --now inspection-agent"
echo "========================================"
