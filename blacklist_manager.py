#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
黑名单管理模块（数据库版本）
管理IP黑名单的添加、移除、过期检查等
"""

import sys
import os
import logging
import threading
from typing import Dict, List
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from database.dao import blacklist_dao

logger = logging.getLogger(__name__)


class BlacklistManager:
    """黑名单管理器（数据库版本）"""

    def __init__(self, use_db: bool = True):
        """
        初始化黑名单管理器

        Args:
            use_db: 是否使用数据库（默认True）
        """
        self.use_db = use_db
        self.lock = threading.Lock()
        logger.info("黑名单管理器初始化完成（使用数据库存储）")

    def add_ip(self, ip: str, expire_hours: int = 24, src_ip: str = None, dst_ip: str = None,
              attack_type: str = None, severity: str = None, rule_name: str = None) -> bool:
        """
        添加IP到黑名单

        Args:
            ip: IP地址
            expire_hours: 过期时间（小时）
            src_ip: 源IP（用于审计）
            dst_ip: 目标IP（用于审计）
            attack_type: 攻击类型
            severity: 严重性
            rule_name: 匹配的规则名称

        Returns:
            bool: 是否添加成功
        """
        with self.lock:
            # 检查是否已存在
            existing = blacklist_dao.get(ip)
            if existing and existing.get('status') == 'active':
                logger.info(f"IP {ip} 已在黑名单中")
                return False

            # 添加到数据库
            result = blacklist_dao.add(
                ip=ip,
                expire_hours=expire_hours,
                src_ip=src_ip,
                dst_ip=dst_ip,
                attack_type=attack_type,
                severity=severity,
                rule_name=rule_name
            )

            if result:
                logger.info(f"IP {ip} 已添加到黑名单管理器，过期时间: {expire_hours}小时")
            return result

    def remove_ip(self, ip: str) -> bool:
        """
        从黑名单移除IP

        Args:
            ip: IP地址

        Returns:
            bool: 是否移除成功
        """
        with self.lock:
            if not blacklist_dao.get(ip):
                logger.warning(f"IP {ip} 不在黑名单中")
                return False

            result = blacklist_dao.remove(ip)
            if result:
                logger.info(f"IP {ip} 已从黑名单移除")
            return result

    def is_blocked(self, ip: str) -> bool:
        """
        检查IP是否被封锁

        Args:
            ip: IP地址

        Returns:
            bool: 是否被封锁
        """
        return blacklist_dao.is_blocked(ip)

    def cleanup_expired(self) -> int:
        """
        清理过期的IP

        Returns:
            int: 清理的IP数量
        """
        return blacklist_dao.cleanup_expired()

    def get_all_ips(self) -> List[Dict]:
        """
        获取所有黑名单IP

        Returns:
            List[Dict]: 黑名单列表
        """
        return blacklist_dao.get_all()

    def get_stats(self) -> dict:
        """
        获取黑名单统计信息

        Returns:
            dict: 统计信息
        """
        return blacklist_dao.get_stats()


# 全局黑名单管理器实例
blacklist_manager = BlacklistManager()
