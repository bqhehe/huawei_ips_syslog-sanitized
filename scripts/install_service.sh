#!/usr/bin/env bash
# -*- coding: utf-8 -*-

"""
安装systemd服务脚本
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
SERVICE_FILE="ips-syslog.service"
SYSTEMD_DIR="/etc/systemd/system"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  安装systemd服务${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查是否以root权限运行
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用root权限运行此脚本${NC}"
    echo -e "${YELLOW}使用: sudo bash scripts/install_service.sh${NC}"
    exit 1
fi

# 检查服务文件是否存在
if [ ! -f "$PROJECT_DIR/$SERVICE_FILE" ]; then
    echo -e "${RED}错误: 服务文件不存在: $SERVICE_FILE${NC}"
    exit 1
fi

# 检查虚拟环境
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo -e "${RED}错误: 虚拟环境不存在${NC}"
    echo -e "${YELLOW}请先创建虚拟环境: python3 -m venv venv${NC}"
    exit 1
fi

# 检查配置文件
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${YELLOW}警告: .env配置文件不存在${NC}"
    echo -e "${YELLOW}正在创建示例配置文件...${NC}"
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo -e "${YELLOW}请编辑.env文件并设置正确的配置${NC}"
    echo ""
fi

# 创建必要的目录
echo -e "${YELLOW}创建必要的目录...${NC}"
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/data"

# 复制服务文件
echo -e "${YELLOW}复制服务文件到systemd目录...${NC}"
cp "$PROJECT_DIR/$SERVICE_FILE" "$SYSTEMD_DIR/"

# 重新加载systemd
echo -e "${YELLOW}重新加载systemd配置...${NC}"
systemctl daemon-reload

# 启用服务
echo -e "${YELLOW}启用服务...${NC}"
systemctl enable ips-syslog.service

# 询问是否立即启动
echo ""
read -p "是否立即启动服务? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}启动服务...${NC}"
    systemctl start ips-syslog.service

    # 检查服务状态
    sleep 2
    if systemctl is-active --quiet ips-syslog.service; then
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}服务安装并启动成功!${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo -e "${YELLOW}常用命令:${NC}"
        echo -e "  查看状态: systemctl status ips-syslog"
        echo -e "  启动服务: systemctl start ips-syslog"
        echo -e "  停止服务: systemctl stop ips-syslog"
        echo -e "  重启服务: systemctl restart ips-syslog"
        echo -e "  查看日志: journalctl -u ips-syslog -f"
    else
        echo -e "${RED}========================================${NC}"
        echo -e "${RED}服务启动失败!${NC}"
        echo -e "${RED}========================================${NC}"
        echo -e "${YELLOW}查看日志: journalctl -u ips-syslog -n 50${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}服务安装成功!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${YELLOW}使用以下命令启动服务:${NC}"
    echo -e "  systemctl start ips-syslog"
    echo ""
    echo -e "${YELLOW}查看状态:${NC}"
    echo -e "  systemctl status ips-syslog"
fi

echo ""