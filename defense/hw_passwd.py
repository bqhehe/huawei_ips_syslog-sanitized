#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
密码管理模块（已废弃）
密码现在通过环境变量或配置文件管理
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


def get_firewall_password() -> str:
    """
    获取防火墙密码
    """
    return Config.FW_PASSWORD


def get_mail_password() -> str:
    """
    获取邮件密码
    """
    return Config.MAIL_PASSWORD


if __name__ == "__main__":
    print("此模块已废弃，请使用环境变量或配置文件管理密码")
    print(f"防火墙密码: {'已设置' if Config.FW_PASSWORD else '未设置'}")
    print(f"邮件密码: {'已设置' if Config.MAIL_PASSWORD else '未设置'}")