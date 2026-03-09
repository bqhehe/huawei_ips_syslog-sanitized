#!/usr/bin/env bash
# -*- coding: utf-8 -*-

"""
自动解封脚本
定期检查并清理过期的黑名单IP
"""

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  自动解封脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 执行清理
echo -e "${YELLOW}正在清理过期的黑名单IP...${NC}"
python3 blacklist_manager.py cleanup

echo ""
echo -e "${GREEN}清理完成${NC}"