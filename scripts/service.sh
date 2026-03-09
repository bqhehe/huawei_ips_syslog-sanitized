#!/usr/bin/env bash
# IPS Syslog 服务管理脚本
# 支持启动、停止、重启、状态查看等操作

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="ips-syslog"
SERVICE_FILE="ips-syslog.service"

# 显示帮助信息
show_help() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  IPS Syslog 服务管理脚本${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
    echo -e "${YELLOW}用法:${NC} bash scripts/service.sh [命令]"
    echo ""
    echo -e "${YELLOW}命令:${NC}"
    echo -e "  ${GREEN}start${NC}      - 启动服务"
    echo -e "  ${GREEN}stop${NC}       - 停止服务"
    echo -e "  ${GREEN}restart${NC}    - 重启服务"
    echo -e "  ${GREEN}status${NC}     - 查看服务状态"
    echo -e "  ${GREEN}logs${NC}       - 查看服务日志 (实时)"
    echo -e "  ${GREEN}enable${NC}     - 设置开机自启动"
    echo -e "  ${GREEN}disable${NC}    - 取消开机自启动"
    echo -e "  ${GREEN}install${NC}    - 安装 systemd 服务"
    echo -e "  ${GREEN}uninstall${NC}  - 卸载 systemd 服务"
    echo -e "  ${GREEN}help${NC}       - 显示此帮助信息"
    echo ""
    echo -e "${YELLOW}示例:${NC}"
    echo -e "  bash scripts/service.sh start"
    echo -e "  bash scripts/service.sh status"
    echo ""
}

# 检查是否使用 systemd
is_systemd_installed() {
    systemctl --version &>/dev/null
}

# 检查服务是否已安装
is_service_installed() {
    [ -f "/etc/systemd/system/${SERVICE_FILE}" ]
}

# 启动服务
start_service() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  启动 IPS Syslog 服务${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    cd "$PROJECT_DIR"

    # 检查虚拟环境
    if [ ! -d "venv" ]; then
        echo -e "${RED}错误: 虚拟环境不存在${NC}"
        exit 1
    fi

    # 检查配置文件
    if [ ! -f ".env" ]; then
        echo -e "${YELLOW}警告: .env 配置文件不存在${NC}"
        if [ -f ".env.example" ]; then
            cp .env.example .env
            echo -e "${GREEN}已创建 .env 配置文件${NC}"
            echo -e "${YELLOW}请编辑 .env 文件设置正确的配置${NC}"
        fi
    fi

    # 创建必要目录
    mkdir -p logs data

    # 优先使用 systemd
    if is_systemd_installed && is_service_installed; then
        echo -e "${YELLOW}使用 systemd 启动服务...${NC}"
        systemctl start $SERVICE_NAME
        sleep 2

        if systemctl is-active --quiet $SERVICE_NAME; then
            echo -e "${GREEN}========================================${NC}"
            echo -e "${GREEN}服务启动成功!${NC}"
            echo -e "${GREEN}========================================${NC}"
            show_status
        else
            echo -e "${RED}========================================${NC}"
            echo -e "${RED}服务启动失败!${NC}"
            echo -e "${RED}========================================${NC}"
            echo -e "${YELLOW}查看日志: journalctl -u $SERVICE_NAME -n 50${NC}"
            exit 1
        fi
    else
        # 手动启动模式
        echo -e "${YELLOW}使用手动模式启动服务...${NC}"

        # 检查是否已在运行
        PIDS=$(ps -ef | grep "python.*syslog_to_huawei_ips.py" | grep -v grep | awk '{print $2}')
        if [ -n "$PIDS" ]; then
            echo -e "${YELLOW}服务已在运行中 (PID: $PIDS)${NC}"
            echo -e "${YELLOW}如需重启，请先执行: bash scripts/service.sh restart${NC}"
            exit 0
        fi

        source venv/bin/activate
        nohup python3 core/syslog_to_huawei_ips.py > logs/service.log 2>&1 &
        SERVICE_PID=$!
        sleep 2

        if ps -p $SERVICE_PID > /dev/null 2>&1; then
            echo -e "${GREEN}========================================${NC}"
            echo -e "${GREEN}服务启动成功!${NC}"
            echo -e "${GREEN}========================================${NC}"
            echo -e "进程 ID: ${SERVICE_PID}"
            echo -e "日志文件: ${PROJECT_DIR}/logs/service.log"
            echo ""
            echo -e "${YELLOW}查看日志:${NC}"
            echo -e "  tail -f logs/service.log"
        else
            echo -e "${RED}========================================${NC}"
            echo -e "${RED}服务启动失败!${NC}"
            echo -e "${RED}========================================${NC}"
            echo -e "${YELLOW}查看日志: cat logs/service.log${NC}"
            exit 1
        fi
    fi
}

# 停止服务
stop_service() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  停止 IPS Syslog 服务${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # 优先使用 systemd
    if is_systemd_installed && systemctl is-active --quiet $SERVICE_NAME 2>/dev/null; then
        echo -e "${YELLOW}使用 systemd 停止服务...${NC}"
        systemctl stop $SERVICE_NAME
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}服务已停止${NC}"
        echo -e "${GREEN}========================================${NC}"
    else
        # 手动停止模式
        echo -e "${YELLOW}使用手动模式停止服务...${NC}"
        PIDS=$(ps -ef | grep "python.*syslog_to_huawei_ips.py" | grep -v grep | awk '{print $2}')

        if [ -n "$PIDS" ]; then
            echo -e "${YELLOW}找到进程: $PIDS${NC}"
            echo "$PIDS" | xargs kill -TERM 2>/dev/null || true
            sleep 2

            # 强制清理剩余进程
            REMAINING=$(ps -ef | grep "python.*syslog_to_huawei_ips.py" | grep -v grep | awk '{print $2}')
            if [ -n "$REMAINING" ]; then
                echo "$REMAINING" | xargs kill -9 2>/dev/null || true
            fi

            echo -e "${GREEN}========================================${NC}"
            echo -e "${GREEN}服务已停止${NC}"
            echo -e "${GREEN}========================================${NC}"
        else
            echo -e "${GREEN}没有找到正在运行的进程${NC}"
        fi
    fi
}

# 重启服务
restart_service() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  重启 IPS Syslog 服务${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    stop_service
    sleep 1
    start_service
}

# 显示状态
show_status() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  IPS Syslog 服务状态${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""

    if is_systemd_installed && is_service_installed; then
        echo -e "${YELLOW}Systemd 服务状态:${NC}"
        systemctl status $SERVICE_NAME --no-pager 2>/dev/null || true
    else
        echo -e "${YELLOW}手动模式服务状态:${NC}"
        PIDS=$(ps -ef | grep "python.*syslog_to_huawei_ips.py" | grep -v grep | awk '{print $2}')
        if [ -n "$PIDS" ]; then
            echo -e "${GREEN}服务正在运行${NC}"
            echo ""
            ps -ef | grep "python.*syslog_to_huawei_ips.py" | grep -v grep
            echo ""
            echo -e "${YELLOW}端口监听状态:${NC}"
            ss -ulnp | grep 514 || netstat -ulnp | grep 514 || echo -e "${YELLOW}无法获取端口信息 (需要root权限)${NC}"
        else
            echo -e "${RED}服务未运行${NC}"
        fi
    fi
    echo ""
}

# 查看日志
show_logs() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  IPS Syslog 服务日志${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
    echo -e "${YELLOW}按 Ctrl+C 退出日志查看${NC}"
    echo ""

    if is_systemd_installed && is_service_installed; then
        journalctl -u $SERVICE_NAME -f
    else
        tail -f "$PROJECT_DIR/logs/service.log"
    fi
}

# 启用开机自启动
enable_service() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  设置开机自启动${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    if ! is_systemd_installed; then
        echo -e "${RED}错误: systemd 不可用${NC}"
        exit 1
    fi

    if ! is_service_installed; then
        echo -e "${YELLOW}服务未安装，正在安装...${NC}"
        install_service
    fi

    systemctl enable $SERVICE_NAME
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}开机自启动已启用${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    systemctl is-enabled $SERVICE_NAME && echo -e "${GREEN}服务已设置为开机自启动${NC}" || echo -e "${RED}启用失败${NC}"
}

# 禁用开机自启动
disable_service() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  取消开机自启动${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    if ! is_systemd_installed; then
        echo -e "${RED}错误: systemd 不可用${NC}"
        exit 1
    fi

    if ! is_service_installed; then
        echo -e "${YELLOW}服务未安装${NC}"
        exit 0
    fi

    systemctl disable $SERVICE_NAME
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}开机自启动已禁用${NC}"
    echo -e "${GREEN}========================================${NC}"
}

# 安装服务
install_service() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  安装 systemd 服务${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}请使用 root 权限运行此命令${NC}"
        echo -e "${YELLOW}使用: sudo bash scripts/service.sh install${NC}"
        exit 1
    fi

    cd "$PROJECT_DIR"

    if [ ! -f "$SERVICE_FILE" ]; then
        echo -e "${RED}错误: 服务文件不存在: $SERVICE_FILE${NC}"
        exit 1
    fi

    # 检查虚拟环境
    if [ ! -d "venv" ]; then
        echo -e "${RED}错误: 虚拟环境不存在${NC}"
        exit 1
    fi

    # 创建必要目录
    mkdir -p logs data

    # 复制服务文件
    echo -e "${YELLOW}安装服务文件...${NC}"
    cp "$SERVICE_FILE" /etc/systemd/system/

    # 重新加载 systemd
    echo -e "${YELLOW}重新加载 systemd 配置...${NC}"
    systemctl daemon-reload

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}服务安装完成!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${YELLOW}后续操作:${NC}"
    echo -e "  启用自启动: bash scripts/service.sh enable"
    echo -e "  启动服务:   bash scripts/service.sh start"
    echo -e "  查看状态:   bash scripts/service.sh status"
}

# 卸载服务
uninstall_service() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  卸载 systemd 服务${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}请使用 root 权限运行此命令${NC}"
        echo -e "${YELLOW}使用: sudo bash scripts/service.sh uninstall${NC}"
        exit 1
    fi

    if ! is_service_installed; then
        echo -e "${YELLOW}服务未安装${NC}"
        exit 0
    fi

    # 停止并禁用服务
    echo -e "${YELLOW}停止服务...${NC}"
    systemctl stop $SERVICE_NAME 2>/dev/null || true
    systemctl disable $SERVICE_NAME 2>/dev/null || true

    # 删除服务文件
    echo -e "${YELLOW}删除服务文件...${NC}"
    rm -f /etc/systemd/system/$SERVICE_FILE

    # 重新加载 systemd
    systemctl daemon-reload

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}服务已卸载${NC}"
    echo -e "${GREEN}========================================${NC}"
}

# 主函数
main() {
    case "${1:-help}" in
        start)
            start_service
            ;;
        stop)
            stop_service
            ;;
        restart)
            restart_service
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        enable)
            enable_service
            ;;
        disable)
            disable_service
            ;;
        install)
            install_service
            ;;
        uninstall)
            uninstall_service
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo -e "${RED}错误: 未知命令 '$1'${NC}"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
