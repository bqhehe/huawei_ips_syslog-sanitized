#!/usr/bin/env bash
# -*- coding: utf-8 -*-

"""
代码格式化脚本
使用black和isort格式化代码
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
echo -e "${BLUE}  代码格式化${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 检查是否安装了格式化工具
echo -e "${YELLOW}检查格式化工具...${NC}"
if ! command -v black &> /dev/null; then
    echo -e "${YELLOW}安装 black...${NC}"
    pip install black
fi

if ! command -v isort &> /dev/null; then
    echo -e "${YELLOW}安装 isort...${NC}"
    pip install isort
fi

# 格式化代码
echo -e "${YELLOW}使用 isort 格式化import语句...${NC}"
isort . --check-only --diff || true
echo -e "${GREEN}运行 isort...${NC}"
isort .

echo ""
echo -e "${YELLOW}使用 black 格式化代码...${NC}"
black . --check --diff || true
echo -e "${GREEN}运行 black...${NC}"
black .

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}代码格式化完成!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}提示: 使用 'git diff' 查看更改${NC}"