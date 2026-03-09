#!/usr/bin/env bash
# -*- coding: utf-8 -*-

"""
运行所有单元测试
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
echo -e "${BLUE}  运行单元测试${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 运行测试
echo -e "${YELLOW}正在运行测试...${NC}"
python3 -m pytest tests/ -v --tb=short

echo ""
if [ $? -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}所有测试通过!${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}测试失败!${NC}"
    echo -e "${RED}========================================${NC}"
    exit 1
fi