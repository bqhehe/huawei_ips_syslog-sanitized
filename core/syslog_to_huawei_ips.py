#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
华为IPS防火墙Syslog自动响应系统 - 主程序
监听UDP 514端口接收防火墙Syslog日志，解析IPS告警并自动进行防御响应
"""

import sys
import os
import logging
from logging.handlers import RotatingFileHandler
import socketserver
import threading
import re
from IPy import IP
import ipaddress
import time
from datetime import datetime, timedelta

# 添加父目录到路径以导入config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from defense.ips_ssh import ips_ssh
from notification.notification_sender import send_ips_alert_notification, send_all_notifications, notification_sender
from utils import global_rate_limiter, global_task_runner, async_task, global_log_buffer
from blacklist_manager import blacklist_manager
from whitelist_manager import whitelist_manager
from health_check import start_health_check
from audit_logger import audit_logger
from alert_deduplicator import alert_deduplicator
from rule_engine import rule_engine
from prometheus_metrics import prometheus_metrics
from web_app import start_web_server
from config_watcher import start_config_watcher


# 配置日志
def setup_logging():
    """配置日志系统"""
    log_dir = os.path.dirname(Config.LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # 创建日志记录器
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO))

    # 清除已有的处理器
    logger.handlers.clear()

    # 文件处理器（带轮转）
    file_handler = RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=Config.LOG_MAX_BYTES,
        backupCount=Config.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger


logger = setup_logging()


# 预处理IP白名单
def preprocess_whitelist(whitelist: list) -> list:
    """
    预处理IP白名单，返回IP对象列表
    """
    ip_objects = []
    for ip_str in whitelist:
        try:
            if '/' in ip_str:
                # 网段
                ip_objects.append(ipaddress.ip_network(ip_str, strict=False))
            else:
                # 单IP
                ip_objects.append(ipaddress.ip_address(ip_str))
        except ValueError as e:
            logger.error(f"无效的IP地址/网段 {ip_str}: {e}")
    return ip_objects


# 全局白名单对象列表（保留用于兼容，但已不再使用）
WHITELIST_OBJS = preprocess_whitelist(Config.IP_WHITELIST)


def format_detect_time(time_str: str) -> str:
    """
    将各种时间格式统一转换为 YYYY-MM-DD HH:MM:SS 格式
    并将 UTC 时间转换为北京时间 (UTC+8)

    支持的输入格式:
    - Jul  3 2023 08:15:57  (英文月份格式)
    - 2023/07/03 16:39:06   (斜杠分隔格式)
    - 2023-07-03 16:39:06   (已标准化格式)

    Args:
        time_str: 原始时间字符串

    Returns:
        str: 标准化后的时间字符串 (YYYY-MM-DD HH:MM:SS)，解析失败返回原字符串
    """
    if not time_str:
        return time_str

    # 如果已经是标准格式，直接返回
    if re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', time_str):
        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        # 转换为北京时间 (UTC+8)
        dt_beijing = dt + timedelta(hours=8)
        return dt_beijing.strftime('%Y-%m-%d %H:%M:%S')

    # 格式1: 2023/07/03 16:39:06 -> 2023-07-03 16:39:06
    match = re.match(r'(\d{4})/(\d{2})/(\d{2})\s+(\d{2}:\d{2}:\d{2})', time_str)
    if match:
        year, month, day, time_part = match.groups()
        dt = datetime.strptime(f"{year}-{month}-{day} {time_part}", '%Y-%m-%d %H:%M:%S')
        # 转换为北京时间 (UTC+8)
        dt_beijing = dt + timedelta(hours=8)
        return dt_beijing.strftime('%Y-%m-%d %H:%M:%S')

    # 格式2: Jul  3 2023 08:15:57 -> 2023-07-03 08:15:57
    # 英文月份映射
    month_map = {
        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
        'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
    }
    match = re.match(r'(\w{3})\s+(\d{1,2})\s+(\d{4})\s+(\d{2}:\d{2}:\d{2})', time_str)
    if match:
        month_abbr, day, year, time_part = match.groups()
        month = month_map.get(month_abbr)
        if month:
            # 补齐日期为两位数
            day = day.zfill(2)
            dt = datetime.strptime(f"{year}-{month}-{day} {time_part}", '%Y-%m-%d %H:%M:%S')
            # 转换为北京时间 (UTC+8)
            dt_beijing = dt + timedelta(hours=8)
            return dt_beijing.strftime('%Y-%m-%d %H:%M:%S')

    # 无法解析，返回原字符串
    return time_str


def is_ip_in_whitelist(ip_str: str) -> bool:
    """
    检查IP是否在白名单中（使用白名单管理器）
    """
    return whitelist_manager.is_whitelisted(ip_str)


def parse_syslog_data(data: str) -> dict:
    """
    解析Syslog数据，提取关键信息
    """
    log_info = {}

    # 使用正则表达式提取所有键值对
    pairs = re.findall(r'(\w+)=("[^"]+"|[^,\s\)]+)', data)
    for key, value in pairs:
        log_info[key] = value.strip('"')

    # 提取时间信息
    time_patterns = [
        r'(\w{3}\s+\d{1,2}\s+\d{4}\s+\d{2}:\d{2}:\d{2})',  # Jul  3 2023 08:15:57
        r'(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})',      # 2023/07/03 16:39:06
    ]
    for pattern in time_patterns:
        match = re.search(pattern, data)
        if match:
            # 标准化时间格式为 YYYY-MM-DD HH:MM:SS
            raw_time = match.group(1)
            log_info['DetectTime'] = format_detect_time(raw_time)
            break

    return log_info


class SyslogUDPHandler(socketserver.BaseRequestHandler):
    """Syslog UDP处理器"""

    def handle(self):
        data = bytes.decode(self.request[0].strip())

        prometheus_metrics.increment_log_received()

        # 判断日志类型
        if '%%01IPS' in data:
            log_type = 'IPS'
        elif '%%01SECLOG' in data:
            log_type = 'SESSION'
        elif '%%01AM' in data:
            log_type = 'AM'
        else:
            log_type = 'OTHER'

        # 解析日志数据（用于缓冲区显示）
        log_info = parse_syslog_data(data)

        # 记录到缓冲区（所有日志都记录）
        global_log_buffer.add(log_type, data, log_info)

        try:
            # 只处理IPS告警，忽略会话日志(%%01SECLOG)等其他类型日志
            if 'IPS' not in data:
                return

            # 提取关键信息
            src_ip = log_info.get('SrcIp')
            dst_ip = log_info.get('DstIp')
            detect_time = log_info.get('DetectTime')
            sign_name = log_info.get('SignName')
            severity = log_info.get('Severity')
            action = log_info.get('Action')

            # 验证必要信息
            if not all([src_ip, dst_ip]):
                logger.warning(f"无法从日志中提取必要信息: {data[:200]}")
                return

            # 速率限制检查
            if not global_rate_limiter.is_allowed(src_ip):
                logger.warning(f"IP {src_ip} 触发速率限制，跳过处理")
                prometheus_metrics.increment_alert_ignored()
                return

            # 记录Prometheus指标
            severity_level = severity or 'unknown'
            attack_type = sign_name or 'unknown'
            prometheus_metrics.increment_alert_received(severity_level, attack_type)

            # 检查IP是否在白名单中
            if is_ip_in_whitelist(src_ip):
                logger.info(f"源IP {src_ip} 在白名单中，不进行处理")
                return

            # 异步执行防御操作
            global_task_runner.submit(
                self.execute_defense,
                src_ip, dst_ip, detect_time, sign_name, severity, action, data
            )

        except Exception as e:
            logger.error(f"处理日志数据时发生错误: {e}\n原始数据: {data[:200]}")
            import traceback
            logger.error(traceback.format_exc())

    def execute_defense(self, src_ip: str, dst_ip: str, detect_time: str,
                       sign_name: str, severity: str, action: str, raw_data: str):
        """
        执行防御操作
        """
        try:
            # 1. 检查IP是否已在黑名单中
            if blacklist_manager.is_blocked(src_ip):
                logger.info(f"IP {src_ip} 已在黑名单中，跳过处理")
                return

            # 2. 使用规则引擎判断处理策略
            attack_type = sign_name or 'unknown'
            severity_level = severity or 'medium'

            rule_name = rule_engine.get_rule_name(attack_type, severity_level)
            should_block = rule_engine.should_block(attack_type, severity_level)
            should_alert = rule_engine.should_alert(attack_type, severity_level)
            expire_hours = rule_engine.get_expire_hours(attack_type, severity_level)

            logger.info(f"匹配规则: {rule_name}, 是否封禁: {should_block}, 是否告警: {should_alert}, 过期时间: {expire_hours}小时")

            # 3. 如果规则要求封禁，则执行封禁操作
            if should_block:
                # 先添加到本地黑名单管理器（确保有记录）
                blacklist_manager.add_ip(src_ip, expire_hours=expire_hours)
                logger.info(f"IP {src_ip} 已添加到本地黑名单管理器，过期时间: {expire_hours}小时")

                # 记录审计日志
                audit_logger.log_block(src_ip, dst_ip, attack_type, severity_level)

                # 尝试添加到防火墙
                logger.info(f"正在将 {src_ip} 添加到防火墙黑名单...")
                if ips_ssh(src_ip, expire_hours):
                    logger.info(f"IP {src_ip} 已成功添加到防火墙黑名单")
                    prometheus_metrics.increment_alert_blocked()
                else:
                    logger.error(f"添加 {src_ip} 到防火墙黑名单失败（已记录到本地黑名单）")
                    audit_logger.log_error('firewall_block_failed', src_ip, 'Failed to add to firewall blacklist')
                    prometheus_metrics.increment_error()
            else:
                logger.info(f"规则引擎判定不封禁IP: {src_ip}")
                prometheus_metrics.increment_alert_ignored()

            # 4. 如果规则要求告警，则发送告警通知
            if should_alert:
                # 检查是否需要发送告警通知（去重）
                if alert_deduplicator.should_alert(src_ip, dst_ip, attack_type):
                    # 使用模板发送告警通知
                    results = send_ips_alert_notification(
                        src_ip=src_ip,
                        dst_ip=dst_ip,
                        detect_time=detect_time,
                        attack_type=attack_type,
                        severity=severity_level,
                        action=action or "N/A",
                        rule_name=rule_name if rule_name != 'default' else None
                    )

                    # 检查是否有任何渠道发送成功
                    if any(results.values()):
                        logger.info(f"告警通知已发送: {results}")
                    else:
                        logger.warning("所有通知渠道发送失败")

                    # 记录Prometheus指标
                    prometheus_metrics.increment_alert_alerted()
                else:
                    logger.info(f"告警去重: {src_ip} 的相同告警在去重窗口内，跳过通知")

            # 5. 记录攻击日志
            self.save_attack_record(raw_data)

        except Exception as e:
            logger.error(f"执行防御操作时发生错误: {e}")
            audit_logger.log_error('defense_error', src_ip, str(e))

    def save_attack_record(self, data: str):
        """
        保存攻击记录到文件和数据库
        """
        try:
            # 1. 写入文件
            attack_dir = os.path.dirname(Config.ATTACK_FILE)
            if attack_dir and not os.path.exists(attack_dir):
                os.makedirs(attack_dir, exist_ok=True)

            with open(Config.ATTACK_FILE, 'a', encoding='utf-8') as f:
                f.write(data + '\n')

            # 2. 同时写入数据库（用于前端告警详情展示）
            try:
                from database.dao import alert_dao
                import re

                # 解析日志数据
                log_info = parse_syslog_data(data)

                src_ip = log_info.get('SrcIp')
                dst_ip = log_info.get('DstIp')
                src_port = log_info.get('SrcPort')
                dst_port = log_info.get('DstPort')
                protocol = log_info.get('Protocol')
                attack_type = log_info.get('SignName') or log_info.get('Attack') or 'Unknown'
                severity = log_info.get('Severity') or 'medium'
                detect_time = log_info.get('DetectTime')

                # 提取原始日志中的时间戳
                time_match = re.search(r'(\w{3}\s+\d+\s+\d{4}\s+\d{2}:\d{2}:\d{2})', data)
                if time_match:
                    detect_time = time_match.group(1)

                # 写入数据库（忽略重复和错误）
                if src_ip and dst_ip:
                    alert_dao.add(
                        src_ip=src_ip,
                        dst_ip=dst_ip,
                        src_port=int(src_port) if src_port and src_port.isdigit() else None,
                        dst_port=int(dst_port) if dst_port and dst_port.isdigit() else None,
                        protocol=protocol,
                        attack_type=attack_type,
                        severity=severity,
                        action='block',
                        raw_log=data[:1000],
                        device='Firewall',
                        detect_time=detect_time
                    )
            except ImportError:
                # 数据库模块不可用时只写入文件
                pass
            except Exception as db_err:
                # 数据库写入失败不影响文件写入
                logger.debug(f"写入告警数据库失败（非致命）: {db_err}")

        except Exception as e:
            logger.error(f"保存攻击记录时发生错误: {e}")


def cleanup_expired_ips():
    """定期清理过期IP的后台任务"""
    while True:
        try:
            time.sleep(3600)  # 每小时清理一次
            count = blacklist_manager.cleanup_expired()
            if count > 0:
                logger.info(f"定期清理: 移除了 {count} 个过期的IP")
        except Exception as e:
            logger.error(f"清理过期IP时发生错误: {e}")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("华为IPS防火墙Syslog自动响应系统启动")
    logger.info("=" * 60)
    logger.info(f"监听地址: {Config.SYSLOG_HOST}:{Config.SYSLOG_PORT}")
    logger.info(f"日志文件: {Config.LOG_FILE}")
    logger.info(f"攻击记录: {Config.ATTACK_FILE}")
    logger.info(f"白名单数量: {len(Config.IP_WHITELIST)}")

    # 启动定期清理过期IP的后台任务
    cleanup_thread = threading.Thread(target=cleanup_expired_ips, daemon=True)
    cleanup_thread.start()
    logger.info("定期清理任务已启动")

    # 启动配置文件热重载
    try:
        start_config_watcher()
        logger.info("配置文件热重载已启动")
    except Exception as e:
        logger.warning(f"启动配置文件热重载失败: {e}")

    # 启动健康检查服务
    try:
        start_health_check(host='0.0.0.0', port=8080)
    except Exception as e:
        logger.warning(f"启动健康检查服务失败: {e}")

    # 启动Web管理界面
    try:
        start_web_server(host='0.0.0.0', port=8081)
    except Exception as e:
        logger.warning(f"启动Web管理界面失败: {e}")

    try:
        # 创建UDP服务器
        server = socketserver.UDPServer(
            (Config.SYSLOG_HOST, Config.SYSLOG_PORT),
            SyslogUDPHandler
        )

        logger.info("服务已启动，等待Syslog数据...")
        server.serve_forever(poll_interval=0.5)

    except (IOError, OSError) as e:
        logger.error(f"服务启动失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("接收到中断信号，正在关闭服务...")
        logger.info("服务已关闭")
        sys.exit(0)


if __name__ == "__main__":
    main()
