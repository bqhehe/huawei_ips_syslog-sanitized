#!/usr/bin/env bash
# -*- coding: utf-8 -*-

"""
卸载脚本 - 移除已部署的服务
"""

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
cat << 'EOF'
╔════════════════════════════════════════════════════════════════╗
║          华为IPS防火墙Syslog系统 - 卸载工具                    ║
╚════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# 检查root权限
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用root权限运行: sudo bash scripts/uninstall.sh${NC}"
    exit 1
fi

# 询问卸载类型
echo "请选择要卸载的部署类型:"
echo "  1) Systemd服务"
echo "  2) Docker容器"
echo "  3) 全部"
echo ""
read -p "请输入选项 [1-3]: " choice

case $choice in
    1|systemd)
        echo -e "${YELLOW}[INFO]${NC} 卸载Systemd服务..."

        # 停止服务
        if systemctl is-active --quiet ips-syslog 2>/dev/null; then
            echo -e "${YELLOW}[INFO]${NC} 停止服务..."
            systemctl stop ips-syslog
        fi

        # 禁用服务
        if systemctl is-enabled --quiet ips-syslog 2>/dev/null; then
            echo -e "${YELLOW}[INFO]${NC} 禁用服务..."
            systemctl disable ips-syslog
        fi

        # 删除服务文件
        if [ -f /etc/systemd/system/ips-syslog.service ]; then
            echo -e "${YELLOW}[INFO]${NC} 删除服务文件..."
            rm -f /etc/systemd/system/ips-syslog.service
            systemctl daemon-reload
        fi

        echo -e "${GREEN}[SUCCESS]${NC} Systemd服务已卸载"
        echo -e "${YELLOW}注意: 项目文件和虚拟环境未被删除，如需删除请手动执行${NC}"
        ;;
    2|docker)
        echo -e "${YELLOW}[INFO]${NC} 卸载Docker容器..."

        # 停止并删除容器
        if docker ps -a | grep -q ips-syslog; then
            echo -e "${YELLOW}[INFO]${NC} 停止并删除容器..."
            docker stop ips-syslog 2>/dev/null || true
            docker rm ips-syslog 2>/dev/null || true
        fi

        # 删除镜像
        if docker images | grep -q ips-syslog; then
            read -p "是否删除Docker镜像? (y/n) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                echo -e "${YELLOW}[INFO]${NC} 删除镜像..."
                docker rmi ips-syslog:latest 2>/dev/null || true
            fi
        fi

        # 删除docker-compose服务（如果有）
        if [ -f docker-compose.yml ]; then
            if docker compose version &> /dev/null; then
                docker compose down 2>/dev/null || true
            elif docker-compose version &> /dev/null; then
                docker-compose down 2>/dev/null || true
            fi
        fi

        echo -e "${GREEN}[SUCCESS]${NC} Docker容器已卸载"
        ;;
    3|all)
        echo -e "${YELLOW}[INFO]${NC} 卸载所有服务..."

        # 卸载Systemd服务
        if systemctl is-active --quiet ips-syslog 2>/dev/null; then
            systemctl stop ips-syslog
        fi
        if systemctl is-enabled --quiet ips-syslog 2>/dev/null; then
            systemctl disable ips-syslog
        fi
        rm -f /etc/systemd/system/ips-syslog.service 2>/dev/null || true
        systemctl daemon-reload 2>/dev/null || true

        # 卸载Docker
        if docker ps -a | grep -q ips-syslog 2>/dev/null; then
            docker stop ips-syslog 2>/dev/null || true
            docker rm ips-syslog 2>/dev/null || true
        fi
        docker rmi ips-syslog:latest 2>/dev/null || true

        echo -e "${GREEN}[SUCCESS]${NC} 所有服务已卸载"

        # 询问是否删除数据
        read -p "是否删除日志和数据文件? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
            echo -e "${YELLOW}[INFO]${NC} 删除日志和数据..."
            rm -rf "$PROJECT_DIR/logs" 2>/dev/null || true
            rm -rf "$PROJECT_DIR/data" 2>/dev/null || true
            echo -e "${GREEN}[SUCCESS]${NC} 数据已删除"
        fi
        ;;
    *)
        echo -e "${RED}无效选项${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}卸载完成!${NC}"
