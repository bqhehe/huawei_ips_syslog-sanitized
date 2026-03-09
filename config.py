#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置管理模块
从环境变量或配置文件读取配置
"""

import os
import logging
from pathlib import Path
from typing import List

# 项目根目录
BASE_DIR = Path(__file__).parent


class Config:
    """配置类"""

    # 防火墙配置
    FW_IP = os.getenv('FW_IP', '192.168.1.1')
    FW_USERNAME = os.getenv('FW_USERNAME', 'admin')
    FW_PASSWORD = os.getenv('FW_PASSWORD', '')

    # 邮件配置
    MAIL_HOST = os.getenv('MAIL_HOST', 'smtp.163.com')
    MAIL_USER = os.getenv('MAIL_USER', 'monitor_user')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_SENDER = os.getenv('MAIL_SENDER', 'monitor@example.com')
    MAIL_RECEIVERS = os.getenv('MAIL_RECEIVERS', 'admin@example.com').split(',')

    # 企业微信配置
    WECHAT_WEBHOOK_URL = os.getenv(
        'WECHAT_WEBHOOK_URL',
        'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your_webhook_key_here'
    )

    # IP白名单
    IP_WHITELIST = os.getenv(
        'IP_WHITELIST',
        '203.0.113.1,203.0.113.2,10.0.0.0/8,10.0.0.88,10.0.0.90,10.0.0.87,192.168.0.0/16,203.0.113.3,172.16.0.88,10.0.0.181,172.16.0.0/16,172.16.0.0/16'
    ).split(',')

    # 日志配置
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', str(BASE_DIR / 'logs' / 'hw-fw-pysyslog.log'))
    LOG_MAX_BYTES = int(os.getenv('LOG_MAX_BYTES', 52428800))  # 50MB (之前是10MB)
    LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', 10))  # 增加备份文件数量

    # 数据文件路径
    ATTACK_FILE = os.getenv('ATTACK_FILE', str(BASE_DIR / 'data' / 'Att.txt'))

    # Syslog服务器配置
    SYSLOG_HOST = os.getenv('SYSLOG_HOST', '0.0.0.0')
    SYSLOG_PORT = int(os.getenv('SYSLOG_PORT', 514))

    # MaxMind GeoIP 配置
    MAXMIND_LICENSE_KEY = os.getenv('MAXMIND_LICENSE_KEY', '')
    MAXMIND_ACCOUNT_ID = os.getenv('MAXMIND_ACCOUNT_ID', '')


def load_env_file(env_file: str = '.env'):
    """
    加载.env文件
    """
    env_path = BASE_DIR / env_file
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    os.environ[key] = value

                    if key == 'FW_PASSWORD':
                        Config.FW_PASSWORD = value
                    elif key == 'MAIL_PASSWORD':
                        Config.MAIL_PASSWORD = value
                    elif key == 'FW_IP':
                        Config.FW_IP = value
                    elif key == 'FW_USERNAME':
                        Config.FW_USERNAME = value
                    elif key == 'MAIL_HOST':
                        Config.MAIL_HOST = value
                    elif key == 'MAIL_USER':
                        Config.MAIL_USER = value
                    elif key == 'MAIL_SENDER':
                        Config.MAIL_SENDER = value
                    elif key == 'MAIL_RECEIVERS':
                        Config.MAIL_RECEIVERS = value.split(',')
                    elif key == 'WECHAT_WEBHOOK_URL':
                        Config.WECHAT_WEBHOOK_URL = value
                    elif key == 'IP_WHITELIST':
                        Config.IP_WHITELIST = value.split(',')
                    elif key == 'LOG_LEVEL':
                        Config.LOG_LEVEL = value
                    elif key == 'LOG_FILE':
                        Config.LOG_FILE = value
                    elif key == 'LOG_MAX_BYTES':
                        Config.LOG_MAX_BYTES = int(value)
                    elif key == 'LOG_BACKUP_COUNT':
                        Config.LOG_BACKUP_COUNT = int(value)
                    elif key == 'ATTACK_FILE':
                        Config.ATTACK_FILE = value
                    elif key == 'SYSLOG_HOST':
                        Config.SYSLOG_HOST = value
                    elif key == 'SYSLOG_PORT':
                        Config.SYSLOG_PORT = int(value)
                    elif key == 'MAXMIND_LICENSE_KEY':
                        Config.MAXMIND_LICENSE_KEY = value
                    elif key == 'MAXMIND_ACCOUNT_ID':
                        Config.MAXMIND_ACCOUNT_ID = value


def update_env_file(updates: dict, env_file: str = '.env'):
    """
    更新.env文件并重新加载配置
    """
    env_path = BASE_DIR / env_file
    
    # 读取现有内容
    lines = []
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    
    # 更新内容
    new_lines = []
    processed_keys = set()
    
    for line in lines:
        line_strip = line.strip()
        if line_strip and not line_strip.startswith('#') and '=' in line_strip:
            key, val = line_strip.split('=', 1)
            key = key.strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                processed_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    
    # 添加新键
    for key, value in updates.items():
        if key not in processed_keys:
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines.append('\n')
            new_lines.append(f"{key}={value}\n")
    
    # 写入文件
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    # 重新加载配置
    load_env_file(env_file)
    return True



# 自动加载.env文件
load_env_file()


def validate_ip(ip: str) -> bool:
    """
    验证IP地址格式
    """
    import ipaddress
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def validate_config() -> bool:
    """
    验证配置是否有效
    """
    errors = []

    # 验证防火墙配置
    if not Config.FW_PASSWORD:
        errors.append("防火墙密码未设置")

    # 验证邮件配置
    if not Config.MAIL_PASSWORD:
        errors.append("邮件密码未设置")

    # 验证IP白名单
    for ip in Config.IP_WHITELIST:
        if '/' in ip:
            # 验证网段
            try:
                import ipaddress
                ipaddress.ip_network(ip, strict=False)
            except ValueError:
                errors.append(f"无效的IP网段: {ip}")
        else:
            # 验证单IP
            if not validate_ip(ip):
                errors.append(f"无效的IP地址: {ip}")

    if errors:
        logging.error("配置验证失败:")
        for error in errors:
            logging.error(f"  - {error}")
        return False

    return True


# 初始化时验证配置
if not validate_config():
    logging.warning("配置存在问题，请检查.env文件")