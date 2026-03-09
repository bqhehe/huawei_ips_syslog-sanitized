#!/usr/bin/env bash
# -*- coding: utf-8 -*-

"""
快速部署脚本 - 使用默认配置快速部署
适用于测试环境或快速部署场景
"""

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo -e "${BLUE}"
cat << 'EOF'
╔════════════════════════════════════════════════════════════════╗
║          华为IPS防火墙Syslog系统 - 快速部署                     ║
╚════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

# 检查root权限
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用root权限运行: sudo bash scripts/quick_deploy.sh${NC}"
    exit 1
fi

# 检查.env文件
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${YELLOW}警告: .env文件不存在，使用快速部署前请先配置${NC}"
    echo -e "${YELLOW}运行完整部署脚本: sudo bash scripts/deploy.sh${NC}"
    exit 1
fi

# 检测部署模式
DEPLOY_MODE=${1:-systemd}

case $DEPLOY_MODE in
    systemd|service)
        echo -e "${GREEN}[INFO]${NC} 使用Systemd服务模式部署..."
        cd "$PROJECT_DIR"

        # 创建虚拟环境（如果不存在）
        if [ ! -d "venv" ]; then
            echo -e "${YELLOW}[INFO]${NC} 创建虚拟环境..."
            python3 -m venv venv
        fi

        # 安装依赖
        echo -e "${YELLOW}[INFO]${NC} 安装依赖..."
        source venv/bin/activate
        pip install --quiet --upgrade pip
        pip install --quiet -r requirements.txt
        deactivate

        # 创建目录
        mkdir -p logs data

        # 安装服务
        echo -e "${YELLOW}[INFO]${NC} 安装systemd服务..."
        sed -i "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|g" ips-syslog.service
        sed -i "s|ExecStart=.*|ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/core/syslog_to_huawei_ips.py|g" ips-syslog.service
        cp ips-syslog.service /etc/systemd/system/

        systemctl daemon-reload
        systemctl enable ips-syslog
        systemctl restart ips-syslog

        sleep 2

        if systemctl is-active --quiet ips-syslog; then
            echo -e "${GREEN}[SUCCESS]${NC} 服务部署成功!"
            echo -e "  状态: ${GREEN}systemctl status ips-syslog${NC}"
            echo -e "  日志: ${GREEN}journalctl -u ips-syslog -f${NC}"
        else
            echo -e "${RED}[ERROR]${NC} 服务启动失败"
            journalctl -u ips-syslog -n 20
            exit 1
        fi
        ;;
    docker)
        echo -e "${GREEN}[INFO]${NC} 使用Docker模式部署..."
        cd "$PROJECT_DIR"

        # 创建目录
        mkdir -p logs data

        # 停止旧容器
        docker stop ips-syslog 2>/dev/null || true
        docker rm ips-syslog 2>/dev/null || true

        # 构建镜像
        echo -e "${YELLOW}[INFO]${NC} 构建Docker镜像..."
        docker build -q -t ips-syslog:latest .

        # 启动容器
        echo -e "${YELLOW}[INFO]${NC} 启动容器..."
        docker run -d \
            --name ips-syslog \
            --restart unless-stopped \
            -p 514:514/udp \
            -p 8080:8080/tcp \
            -p 8081:8081/tcp \
            -v "$PROJECT_DIR/logs:/app/logs" \
            -v "$PROJECT_DIR/data:/app/data" \
            -v "$PROJECT_DIR/.env:/app/.env:ro" \
            -e TZ=Asia/Shanghai \
            --cap-add=NET_BIND_SERVICE \
            ips-syslog:latest

        sleep 3

        if docker ps | grep -q ips-syslog; then
            echo -e "${GREEN}[SUCCESS]${NC} 容器部署成功!"
            echo -e "  状态: ${GREEN}docker ps${NC}"
            echo -e "  日志: ${GREEN}docker logs -f ips-syslog${NC}"
        else
            echo -e "${RED}[ERROR]${NC} 容器启动失败"
            docker logs ips-syslog
            exit 1
        fi
        ;;
    *)
        echo -e "${RED}用法: $0 [systemd|docker]${NC}"
        echo -e "  systemd  - 使用systemd服务部署（默认）"
        echo -e "  docker   - 使用docker容器部署"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}部署完成! 端口: 514/udp, 8080/tcp, 8081/tcp${NC}"
