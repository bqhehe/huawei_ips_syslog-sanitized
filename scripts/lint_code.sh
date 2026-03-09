#!/usr/bin/env bash
# -*- coding: utf-8 -*-

"""
代码检查脚本
使用pylint和flake8检查代码质量
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
echo -e "${BLUE}  代码检查${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 检查是否安装了检查工具
echo -e "${YELLOW}检查代码质量工具...${NC}"
if ! command -v pylint &> /dev/null; then
    echo -e "${YELLOW}安装 pylint...${NC}"
    pip install pylint
fi

if ! command -v flake8 &> /dev/null; then
    echo -e "${YELLOW}安装 flake8...${NC}"
    pip install flake8
fi

# 运行flake8
echo -e "${YELLOW}运行 flake8...${NC}"
flake8 core/ defense/ notification/ utils.py blacklist_manager.py audit_logger.py health_check.py alert_deduplicator.py rule_engine.py config.py || true

echo ""

# 运行pylint
echo -e "${YELLOW}运行 pylint...${NC}"
pylint core/ defense/ notification/ utils.py blacklist_manager.py audit_logger.py health_check.py alert_deduplicator.py rule_engine.py config.py || true

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}代码检查完成!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}提示: 请查看上面的输出，修复发现的问题${NC}"