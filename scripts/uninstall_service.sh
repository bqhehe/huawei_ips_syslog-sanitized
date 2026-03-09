#!/usr/bin/env bash
# -*- coding: utf-8 -*-

"""
卸载systemd服务脚本
"""

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SERVICE_NAME="ips-syslog"
SYSTEMD_DIR="/etc/systemd/system"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  卸载systemd服务${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查是否以root权限运行
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用root权限运行此脚本${NC}"
    echo -e "${YELLOW}使用: sudo bash scripts/uninstall_service.sh${NC}"
    exit 1
fi

# 检查服务是否存在
if [ ! -f "$SYSTEMD_DIR/$SERVICE_NAME.service" ]; then
    echo -e "${YELLOW}服务不存在: $SERVICE_NAME${NC}"
    exit 0
fi

# 停止服务
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${YELLOW}停止服务...${NC}"
    systemctl stop $SERVICE_NAME
fi

# 禁用服务
echo -e "${YELLOW}禁用服务...${NC}"
systemctl disable $SERVICE_NAME

# 删除服务文件
echo -e "${YELLOW}删除服务文件...${NC}"
rm -f "$SYSTEMD_DIR/$SERVICE_NAME.service"

# 重新加载systemd
echo -e "${YELLOW}重新加载systemd配置...${NC}"
systemctl daemon-reload

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}服务卸载成功!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""