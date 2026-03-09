#!/usr/bin/env bash
# -*- coding: utf-8 -*-

"""
华为IPS防火墙Syslog自动响应系统 - 一键部署脚本
支持Systemd和Docker两种部署方式
"""

set -e

# =============================================================================
# 颜色定义
# =============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# =============================================================================
# 全局变量
# =============================================================================
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_MODE=""
LOG_FILE="/tmp/ips-deploy-$(date +%Y%m%d_%H%M%S).log"

# =============================================================================
# 工具函数
# =============================================================================

print_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║        华为IPS防火墙Syslog自动响应系统 - 一键部署工具          ║
║                   IPS Syslog Auto Response System              ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1" | tee -a "$LOG_FILE"
}

# =============================================================================
# 系统检测函数
# =============================================================================

detect_os() {
    log_step "检测操作系统..."

    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
        log_info "检测到操作系统: $OS $OS_VERSION"
    else
        log_error "无法检测操作系统类型"
        exit 1
    fi
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "此脚本需要root权限运行"
        echo -e "${YELLOW}请使用: sudo bash scripts/deploy.sh${NC}"
        exit 1
    fi
}

check_python() {
    log_step "检查Python版本..."

    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

        log_info "检测到Python版本: $PYTHON_VERSION"

        if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
            log_error "Python版本过低，需要Python 3.10或更高版本"
            return 1
        fi
    else
        log_error "未检测到Python 3"
        return 1
    fi

    return 0
}

check_docker() {
    log_step "检查Docker环境..."

    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version | awk '{print $3}' | tr -d ',')
        log_info "检测到Docker版本: $DOCKER_VERSION"
        return 0
    else
        log_warn "未检测到Docker"
        return 1
    fi
}

check_ports() {
    log_step "检查端口占用..."

    PORTSoccupied=()

    for port in 514 8080 8081; do
        if ss -tuln | grep -q ":$port "; then
            PORTSoccupied+=($port)
        fi
    done

    if [ ${#PORTSoccupied[@]} -gt 0 ]; then
        log_warn "以下端口已被占用: ${PORTSoccupied[*]}"
        read -p "是否继续部署? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "部署已取消"
            exit 0
        fi
    else
        log_info "所有端口均可用"
    fi
}

# =============================================================================
# 依赖安装函数
# =============================================================================

install_system_dependencies() {
    log_step "安装系统依赖..."

    case $OS in
        centos|rhel|rocky|almalinux)
            yum install -y python3 python3-pip python3-venv git curl firewalld
            ;;
        ubuntu|debian)
            apt-get update
            apt-get install -y python3 python3-pip python3-venv git curl ufw
            ;;
        *)
            log_error "不支持的操作系统: $OS"
            exit 1
            ;;
    esac

    log_info "系统依赖安装完成"
}

install_docker() {
    log_step "安装Docker和Docker Compose..."

    case $OS in
        centos|rhel|rocky|almalinux)
            # 安装Docker
            yum install -y yum-utils
            yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

            # 启动Docker
            systemctl start docker
            systemctl enable docker
            ;;
        ubuntu|debian)
            # 更新包索引
            apt-get update

            # 安装依赖
            apt-get install -y ca-certificates curl gnupg

            # 添加Docker GPG密钥
            install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/$OS/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
            chmod a+r /etc/apt/keyrings/docker.gpg

            # 添加Docker仓库
            echo \
              "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$OS \
              $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
              tee /etc/apt/sources.list.d/docker.list > /dev/null

            # 安装Docker
            apt-get update
            apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

            # 启动Docker
            systemctl start docker
            systemctl enable docker
            ;;
        *)
            log_error "不支持的操作系统: $OS"
            exit 1
            ;;
    esac

    log_info "Docker安装完成"
}

# =============================================================================
# 配置函数
# =============================================================================

configure_env() {
    log_step "配置环境变量..."

    ENV_FILE="$PROJECT_DIR/.env"

    # 如果.env文件已存在，询问是否重新配置
    if [ -f "$ENV_FILE" ]; then
        log_warn ".env文件已存在"
        read -p "是否重新配置? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "使用现有配置"
            return 0
        fi
        # 备份现有配置
        cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        log_info "现有配置已备份"
    else
        # 复制示例配置
        if [ -f "$PROJECT_DIR/.env.example" ]; then
            cp "$PROJECT_DIR/.env.example" "$ENV_FILE"
        else
            touch "$ENV_FILE"
        fi
    fi

    echo ""
    echo -e "${BOLD}==================== 配置向导 ====================${NC}"
    echo ""

    # 防火墙配置
    echo -e "${CYAN}--- 防火墙配置 ---${NC}"
    read -p "防火墙IP地址 [FW_IP]: " fw_ip
    read -p "SSH用户名 [FW_USERNAME]: " fw_username
    read -s -p "SSH密码 [FW_PASSWORD]: " fw_password
    echo ""

    # 邮件配置
    echo ""
    echo -e "${CYAN}--- 邮件通知配置 ---${NC}"
    read -p "SMTP服务器 [MAIL_HOST, 默认smtp.163.com]: " mail_host
    mail_host=${mail_host:-smtp.163.com}
    read -p "SMTP用户名 [MAIL_USER]: " mail_user
    read -s -p "SMTP密码 [MAIL_PASSWORD]: " mail_password
    echo ""
    read -p "发件人邮箱 [MAIL_SENDER]: " mail_sender
    read -p "收件人邮箱 [MAIL_RECEIVERS, 多个用逗号分隔]: " mail_receivers

    # 企业微信配置
    echo ""
    echo -e "${CYAN}--- 企业微信通知配置（可选） ---${NC}"
    read -p "企业微信Webhook URL [WECHAT_WEBHOOK_URL, 留空跳过]: " wechat_webhook

    # IP白名单
    echo ""
    echo -e "${CYAN}--- IP白名单配置 ---${NC}"
    echo "输入白名单IP地址或网段，多个用逗号分隔"
    echo "例如: 10.0.0.0/8,192.168.1.100,172.16.0.0/16"
    read -p "IP白名单 [IP_WHITELIST]: " ip_whitelist

    # 其他配置
    echo ""
    echo -e "${CYAN}--- 其他配置 ---${NC}"
    read -p "日志级别 [LOG_LEVEL, 默认INFO]: " log_level
    log_level=${log_level:-INFO}

    # 写入配置文件
    cat > "$ENV_FILE" << EOF
# 防火墙配置
FW_IP=${fw_ip}
FW_USERNAME=${fw_username}
FW_PASSWORD=${fw_password}

# 邮件配置
MAIL_HOST=${mail_host}
MAIL_USER=${mail_user}
MAIL_PASSWORD=${mail_password}
MAIL_SENDER=${mail_sender}
MAIL_RECEIVERS=${mail_receivers}

# 企业微信配置
${wechat_webhook:+WECHAT_WEBHOOK_URL=${wechat_webhook}}

# IP白名单
IP_WHITELIST=${ip_whitelist}

# 日志配置
LOG_LEVEL=${log_level}
LOG_FILE=logs/hw-fw-pysyslog.log
LOG_MAX_BYTES=52428800
LOG_BACKUP_COUNT=10

# 数据文件路径
ATTACK_FILE=data/Att.txt

# Syslog服务器配置
SYSLOG_HOST=0.0.0.0
SYSLOG_PORT=514
EOF

    log_info "配置文件已创建: $ENV_FILE"
    echo ""
    read -p "是否需要编辑配置文件? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ${EDITOR:-vi} "$ENV_FILE"
    fi
}

# =============================================================================
# Systemd部署函数
# =============================================================================

deploy_systemd() {
    log_step "使用Systemd方式部署..."

    # 1. 创建虚拟环境
    log_info "创建Python虚拟环境..."
    cd "$PROJECT_DIR"
    python3 -m venv venv

    # 2. 安装依赖
    log_info "安装Python依赖..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    deactivate

    # 3. 创建必要目录
    log_info "创建必要目录..."
    mkdir -p "$PROJECT_DIR/logs"
    mkdir -p "$PROJECT_DIR/data"

    # 4. 复制systemd服务文件
    log_info "安装systemd服务..."
    cp "$PROJECT_DIR/ips-syslog.service" /etc/systemd/system/

    # 5. 修改服务文件中的路径（如果需要）
    sed -i "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|g" /etc/systemd/system/ips-syslog.service
    sed -i "s|Environment=\"PYTHONPATH=.*|Environment=\"PYTHONPATH=$PROJECT_DIR:$PROJECT_DIR/venv/lib/python3.*/site-packages\"|g" /etc/systemd/system/ips-syslog.service
    sed -i "s|ExecStart=.*|ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/core/syslog_to_huawei_ips.py|g" /etc/systemd/system/ips-syslog.service

    # 6. 重新加载systemd
    log_info "重新加载systemd配置..."
    systemctl daemon-reload

    # 7. 启用服务
    log_info "启用开机自启..."
    systemctl enable ips-syslog.service

    # 8. 启动服务
    log_info "启动服务..."
    systemctl start ips-syslog.service

    # 9. 等待服务启动
    sleep 3

    # 10. 检查服务状态
    if systemctl is-active --quiet ips-syslog.service; then
        log_info "服务启动成功!"
    else
        log_error "服务启动失败，请查看日志: journalctl -u ips-syslog -n 50"
        exit 1
    fi
}

# =============================================================================
# Docker部署函数
# =============================================================================

deploy_docker() {
    log_step "使用Docker方式部署..."

    # 1. 创建必要目录
    log_info "创建必要目录..."
    mkdir -p "$PROJECT_DIR/logs"
    mkdir -p "$PROJECT_DIR/data"

    # 2. 构建镜像
    log_info "构建Docker镜像..."
    cd "$PROJECT_DIR"
    docker build -t ips-syslog:latest .

    # 3. 停止并删除旧容器（如果存在）
    if docker ps -a | grep -q ips-syslog; then
        log_info "停止并删除旧容器..."
        docker stop ips-syslog 2>/dev/null || true
        docker rm ips-syslog 2>/dev/null || true
    fi

    # 4. 启动容器
    log_info "启动Docker容器..."
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
        -e PYTHONUNBUFFERED=1 \
        --cap-add=NET_BIND_SERVICE \
        ips-syslog:latest

    # 5. 等待容器启动
    sleep 3

    # 6. 检查容器状态
    if docker ps | grep -q ips-syslog; then
        log_info "容器启动成功!"
    else
        log_error "容器启动失败，请查看日志: docker logs ips-syslog"
        exit 1
    fi
}

# =============================================================================
# 验证函数
# =============================================================================

verify_deployment() {
    log_step "验证部署..."

    echo ""
    echo -e "${BOLD}==================== 部署验证 ====================${NC}"
    echo ""

    # 1. 检查服务状态
    if [ "$DEPLOY_MODE" = "systemd" ]; then
        if systemctl is-active --quiet ips-syslog.service; then
            echo -e "${GREEN}[✓]${NC} 服务运行正常"
        else
            echo -e "${RED}[✗]${NC} 服务未运行"
        fi
    else
        if docker ps | grep -q ips-syslog; then
            echo -e "${GREEN}[✓]${NC} 容器运行正常"
        else
            echo -e "${RED}[✗]${NC} 容器未运行"
        fi
    fi

    # 2. 检查端口监听
    if ss -tuln | grep -q ":514 "; then
        echo -e "${GREEN}[✓]${NC} Syslog端口(514/UDP)监听正常"
    else
        echo -e "${RED}[✗]${NC} Syslog端口(514/UDP)未监听"
    fi

    if ss -tuln | grep -q ":8080 "; then
        echo -e "${GREEN}[✓]${NC} 健康检查端口(8080/TCP)监听正常"
    else
        echo -e "${RED}[✗]${NC} 健康检查端口(8080/TCP)未监听"
    fi

    if ss -tuln | grep -q ":8081 "; then
        echo -e "${GREEN}[✓]${NC} Web管理端口(8081/TCP)监听正常"
    else
        echo -e "${YELLOW}[!]${NC} Web管理端口(8081/TCP)未监听（可选）"
    fi

    # 3. 测试健康检查
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo -e "${GREEN}[✓]${NC} 健康检查接口正常"
    else
        echo -e "${YELLOW}[!]${NC} 健康检查接口未响应（可能还在启动中）"
    fi

    # 4. 检查日志文件
    if [ -f "$PROJECT_DIR/logs/hw-fw-pysyslog.log" ]; then
        echo -e "${GREEN}[✓]${NC} 日志文件已创建"
    else
        echo -e "${YELLOW}[!]${NC} 日志文件未创建（可能还在初始化）"
    fi

    echo ""
}

print_success() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                   部署完成！                                     ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BOLD}部署方式:${NC} $DEPLOY_MODE"
    echo -e "${BOLD}项目目录:${NC} $PROJECT_DIR"
    echo -e "${BOLD}日志文件:${NC} $LOG_FILE"
    echo ""
    echo -e "${BOLD}==================== 服务信息 ====================${NC}"
    echo -e "  Syslog接收:     ${CYAN}UDP 514${NC}"
    echo -e "  健康检查:       ${CYAN}TCP 8080${NC}  →  http://$(hostname -I | awk '{print $1}'):8080/health"
    echo -e "  Web管理界面:    ${CYAN}TCP 8081${NC}  →  http://$(hostname -I | awk '{print $1}'):8081"
    echo ""
    echo -e "${BOLD}==================== 常用命令 ====================${NC}"

    if [ "$DEPLOY_MODE" = "systemd" ]; then
        echo -e "  查看状态:   ${YELLOW}systemctl status ips-syslog${NC}"
        echo -e "  启动服务:   ${YELLOW}systemctl start ips-syslog${NC}"
        echo -e "  停止服务:   ${YELLOW}systemctl stop ips-syslog${NC}"
        echo -e "  重启服务:   ${YELLOW}systemctl restart ips-syslog${NC}"
        echo -e "  查看日志:   ${YELLOW}journalctl -u ips-syslog -f${NC}"
        echo -e "  应用日志:   ${YELLOW}tail -f logs/hw-fw-pysyslog.log${NC}"
    else
        echo -e "  查看状态:   ${YELLOW}docker ps -a | grep ips-syslog${NC}"
        echo -e "  查看日志:   ${YELLOW}docker logs -f ips-syslog${NC}"
        echo -e "  启动容器:   ${YELLOW}docker start ips-syslog${NC}"
        echo -e "  停止容器:   ${YELLOW}docker stop ips-syslog${NC}"
        echo -e "  重启容器:   ${YELLOW}docker restart ips-syslog${NC}"
        echo -e "  进入容器:   ${YELLOW}docker exec -it ips-syslog bash${NC}"
    fi

    echo ""
    echo -e "${BOLD}==================== 下一步 ====================${NC}"
    echo -e "  1. 配置华为防火墙发送Syslog到此服务器 (UDP 514)"
    echo -e "  2. 访问Web管理界面进行配置和监控: http://$(hostname -I | awk '{print $1}'):8081"
    echo -e "  3. 查看详细部署文档: ${CYAN}cat DEPLOYMENT.md${NC}"
    echo ""
}

# =============================================================================
# 主函数
# =============================================================================

main() {
    # 打印横幅
    print_banner

    # 检查root权限
    check_root

    # 检测操作系统
    detect_os

    # 选择部署模式
    echo ""
    echo -e "${BOLD}请选择部署模式:${NC}"
    echo "  1) Systemd服务部署 (推荐用于物理机/虚拟机)"
    echo "  2) Docker部署 (推荐用于容器化环境)"
    echo "  3) Docker Compose部署 (使用docker-compose.yml)"
    echo ""
    read -p "请输入选项 [1-3]: " deploy_choice

    case $deploy_choice in
        1)
            DEPLOY_MODE="systemd"
            ;;
        2)
            DEPLOY_MODE="docker"
            ;;
        3)
            DEPLOY_MODE="docker-compose"
            ;;
        *)
            log_error "无效选项"
            exit 1
            ;;
    esac

    log_info "选择部署模式: $DEPLOY_MODE"

    # 检查端口
    check_ports

    # 根据部署模式安装依赖
    if [ "$DEPLOY_MODE" = "systemd" ]; then
        if ! check_python; then
            log_error "Python环境检查失败"
            exit 1
        fi
        install_system_dependencies
    elif [ "$DEPLOY_MODE" = "docker" ]; then
        if ! check_docker; then
            log_warn "Docker未安装，将自动安装"
            install_docker
        fi
    elif [ "$DEPLOY_MODE" = "docker-compose" ]; then
        if ! check_docker; then
            log_warn "Docker未安装，将自动安装"
            install_docker
        fi
    fi

    # 配置环境变量
    configure_env

    # 执行部署
    case $DEPLOY_MODE in
        systemd)
            deploy_systemd
            ;;
        docker)
            deploy_docker
            ;;
        docker-compose)
            deploy_docker_compose
            ;;
    esac

    # 验证部署
    verify_deployment

    # 打印成功信息
    print_success
}

# Docker Compose部署函数
deploy_docker_compose() {
    log_step "使用Docker Compose方式部署..."

    # 1. 创建必要目录
    log_info "创建必要目录..."
    mkdir -p "$PROJECT_DIR/logs"
    mkdir -p "$PROJECT_DIR/data"

    # 2. 使用docker-compose启动
    log_info "使用Docker Compose启动服务..."
    cd "$PROJECT_DIR"

    # 检查docker compose命令
    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE="docker compose"
    elif docker-compose version &> /dev/null; then
        DOCKER_COMPOSE="docker-compose"
    else
        log_error "未找到docker-compose命令"
        exit 1
    fi

    # 构建并启动
    $DOCKER_COMPOSE up -d --build

    # 等待服务启动
    sleep 5

    # 检查服务状态
    if $DOCKER_COMPOSE ps | grep -q "ips-syslog.*Up"; then
        log_info "服务启动成功!"
    else
        log_error "服务启动失败"
        $DOCKER_COMPOSE logs
        exit 1
    fi
}

# 运行主函数
main "$@"
