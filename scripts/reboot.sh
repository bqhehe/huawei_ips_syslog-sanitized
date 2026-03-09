#!/usr/bin/env bash
# -*- coding: utf-8 -*-

"""
服务重启脚本
重启Syslog监控服务
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
echo -e "${BLUE}  华为IPS防火墙Syslog自动响应系统${NC}"
echo -e "${BLUE}  服务重启脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo -e "${RED}错误: 虚拟环境不存在${NC}"
    exit 1
fi

# 激活虚拟环境
echo -e "${YELLOW}激活虚拟环境...${NC}"
source venv/bin/activate

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
    echo -e "${GREEN}进程已停止${NC}"
else
    echo -e "${GREEN}没有找到正在运行的进程${NC}"
fi

echo ""

# 检查配置文件
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}警告: .env配置文件不存在${NC}"
    echo -e "${YELLOW}正在创建示例配置文件...${NC}"
    cp .env.example .env
    echo -e "${GREEN}示例配置文件已创建: .env${NC}"
    echo -e "${YELLOW}请编辑.env文件并设置正确的配置${NC}"
    echo ""
fi

# 启动服务
echo -e "${YELLOW}正在启动服务...${NC}"
nohup python3 core/syslog_to_huawei_ips.py > logs/service.log 2>&1 &
SERVICE_PID=$!

sleep 2

# 检查服务是否启动成功
if ps -p $SERVICE_PID > /dev/null; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}服务启动成功!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo -e "进程ID: ${SERVICE_PID}"
    echo -e "日志文件: ${PROJECT_DIR}/logs/service.log"
    echo -e "Syslog日志: ${PROJECT_DIR}/logs/hw-fw-pysyslog.log"
    echo ""
    echo -e "${YELLOW}查看日志:${NC}"
    echo -e "  tail -f logs/service.log"
    echo -e "  tail -f logs/hw-fw-pysyslog.log"
    echo ""
    echo -e "${YELLOW}停止服务:${NC}"
    echo -e "  bash scripts/stop.sh"
    echo ""
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}服务启动失败!${NC}"
    echo -e "${RED}========================================${NC}"
    echo -e "请查看日志文件: ${PROJECT_DIR}/logs/service.log"
    exit 1
fi