#!/usr/bin/env bash
# -*- coding: utf-8 -*-

"""
服务停止脚本
停止Syslog监控服务
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

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  华为IPS防火墙Syslog自动响应系统${NC}"
echo -e "${BLUE}  服务停止脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 查找正在运行的进程
echo -e "${YELLOW}查找正在运行的进程...${NC}"
PIDS=$(ps -ef | grep "python.*syslog_to_huawei_ips.py" | grep -v grep | awk '{print $2}')

if [ -n "$PIDS" ]; then
    echo -e "${YELLOW}找到以下进程:${NC}"
    ps -ef | grep "python.*syslog_to_huawei_ips.py" | grep -v grep
    echo ""
    echo -e "${YELLOW}正在停止进程...${NC}"
    echo "$PIDS" | xargs kill -9
    sleep 1

    # 验证进程是否已停止
    REMAINING=$(ps -ef | grep "python.*syslog_to_huawei_ips.py" | grep -v grep | awk '{print $2}')
    if [ -z "$REMAINING" ]; then
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}服务已成功停止${NC}"
        echo -e "${GREEN}========================================${NC}"
    else
        echo -e "${RED}========================================${NC}"
        echo -e "${RED}部分进程未能停止${NC}"
        echo -e "${RED}========================================${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}没有找到正在运行的进程${NC}"
    echo -e "${GREEN}========================================${NC}"
fi

echo ""