#!/bin/bash
# =============================================
#  CTF Lab 环境生成脚本
#  用法: bash generate_lab.sh
#  生成随机 flag 并配置 lab 环境
# =============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SHARED_DIR="$SCRIPT_DIR/shared"
ENV_FILE="$SCRIPT_DIR/.env"

mkdir -p "$SHARED_DIR"

echo "=== CTF Lab 环境生成 ==="

# 生成 3 个随机 flag
FLAG1="FLAG{$(openssl rand -hex 16)}"
FLAG2="FLAG{$(openssl rand -hex 12)}"
FLAG3="FLAG{$(openssl rand -hex 8)}"

echo "生成的 Flag:"
echo "  Flag 1 (Easy):   $FLAG1"
echo "  Flag 2 (Medium): $FLAG2"
echo "  Flag 3 (Hard):   $FLAG3"
echo ""

# 写入 .env（docker-compose 读取）
cat > "$ENV_FILE" << EOF
# CTF Lab Flags — 由 generate_lab.sh 自动生成
FLAG1=$FLAG1
FLAG2=$FLAG2
FLAG3=$FLAG3
EOF

echo ".env 已写入: $ENV_FILE"

# 写入 submission server 的 flag 文件
cat > "$SHARED_DIR/flags.txt" << EOF
$FLAG1
$FLAG2
$FLAG3
EOF

echo "flags.txt 已写入: $SHARED_DIR/flags.txt"
echo ""
echo "=== 完成 ==="
echo "运行 'docker compose up -d --build' 启动 lab"
echo "运行 'docker compose down -v' 清除环境"
