#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
白名单管理模块（数据库版本）
管理IP白名单的添加、移除等操作
白名单中的IP不会被系统封禁
"""

import sys
import os
import logging
import threading
import ipaddress
from typing import Dict, List, Optional, Union
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from database.dao import whitelist_dao, audit_dao
from audit_logger import audit_logger

logger = logging.getLogger(__name__)


class WhitelistManager:
    """白名单管理器（数据库版本）"""

    def __init__(self, use_db: bool = True):
        """
        初始化白名单管理器

        Args:
            use_db: 是否使用数据库（默认True）
        """
        self.use_db = use_db
        self.lock = threading.Lock()
        # 缓存白名单用于快速查询
        self._cache: List[Union[ipaddress.IPv4Address, ipaddress.IPv4Network]] = []
        self._cache_timestamp = None
        self._cache_ttl = 60  # 缓存有效期60秒
        self._build_cache()
        logger.info("白名单管理器初始化完成（使用数据库存储）")

    def _build_cache(self):
        """构建白名单缓存"""
        if not self.use_db:
            # 使用配置文件中的白名单
            self._cache = self._parse_whitelist(Config.IP_WHITELIST)
            self._cache_timestamp = datetime.now()
            return

        try:
            # 从数据库加载白名单
            whitelist_entries = whitelist_dao.get_all()
            ip_list = [entry['ip_or_cidr'] for entry in whitelist_entries]
            self._cache = self._parse_whitelist(ip_list)
            self._cache_timestamp = datetime.now()
            logger.debug(f"白名单缓存已更新，共 {len(self._cache)} 条")
        except Exception as e:
            logger.error(f"构建白名单缓存失败: {e}")

    def _parse_whitelist(self, whitelist: List[str]) -> List[Union[ipaddress.IPv4Address, ipaddress.IPv4Network]]:
        """解析白名单列表为IP对象"""
        ip_objects = []
        for ip_str in whitelist:
            try:
                ip_str = ip_str.strip()
                if not ip_str:
                    continue
                if '/' in ip_str:
                    # 网段
                    ip_objects.append(ipaddress.ip_network(ip_str, strict=False))
                else:
                    # 单个IP
                    ip_objects.append(ipaddress.ip_address(ip_str))
            except ValueError as e:
                logger.warning(f"无效的白名单IP: {ip_str}, 错误: {e}")
        return ip_objects

    def _refresh_cache_if_needed(self):
        """如果缓存过期则刷新"""
        if self._cache_timestamp is None:
            self._build_cache()
            return

        age = (datetime.now() - self._cache_timestamp).total_seconds()
        if age > self._cache_ttl:
            self._build_cache()

    def add_ip(self, ip_or_cidr: str, description: str = None, added_by: str = 'admin') -> Dict:
        """
        添加IP或网段到白名单

        Args:
            ip_or_cidr: IP地址或CIDR网段
            description: 描述
            added_by: 添加者

        Returns:
            Dict: 操作结果
        """
        with self.lock:
            # 验证IP格式
            try:
                if '/' in ip_or_cidr:
                    ipaddress.ip_network(ip_or_cidr, strict=False)
                else:
                    ipaddress.ip_address(ip_or_cidr)
            except ValueError:
                return {'success': False, 'message': f'无效的IP或网段格式: {ip_or_cidr}'}

            # 添加到数据库
            if self.use_db:
                if whitelist_dao.add(ip_or_cidr, description, 'manual', added_by):
                    self._build_cache()  # 刷新缓存
                    logger.info(f"已添加到白名单: {ip_or_cidr}")
                    audit_logger.log('whitelist_add', ip_or_cidr, {'description': description})
                    return {'success': True, 'message': f'已添加到白名单: {ip_or_cidr}'}
                else:
                    return {'success': False, 'message': '添加失败（可能已存在）'}
            else:
                # 不使用数据库时，只能记录日志
                logger.info(f"白名单添加（仅记录）: {ip_or_cidr}")
                return {'success': True, 'message': f'已记录（数据库未启用）: {ip_or_cidr}'}

    def remove_ip(self, ip_or_cidr: str) -> Dict:
        """
        从白名单移除IP或网段

        Args:
            ip_or_cidr: IP地址或CIDR网段

        Returns:
            Dict: 操作结果
        """
        with self.lock:
            if not self.is_whitelisted(ip_or_cidr):
                return {'success': False, 'message': f'{ip_or_cidr} 不在白名单中'}

            if self.use_db:
                if whitelist_dao.remove(ip_or_cidr):
                    self._build_cache()  # 刷新缓存
                    logger.info(f"已从白名单移除: {ip_or_cidr}")
                    audit_logger.log('whitelist_remove', ip_or_cidr, {})
                    return {'success': True, 'message': f'已从白名单移除: {ip_or_cidr}'}
                else:
                    return {'success': False, 'message': '移除失败'}
            else:
                return {'success': False, 'message': '数据库未启用，无法移除'}

    def is_whitelisted(self, ip: str) -> bool:
        """
        检查IP是否在白名单中

        Args:
            ip: IP地址

        Returns:
            bool: 是否在白名单中
        """
        self._refresh_cache_if_needed()

        try:
            check_ip = ipaddress.ip_address(ip)
            for whitelist_item in self._cache:
                if isinstance(whitelist_item, ipaddress.IPv4Network):
                    if check_ip in whitelist_item:
                        return True
                elif isinstance(whitelist_item, ipaddress.IPv4Address):
                    if check_ip == whitelist_item:
                        return True
            return False
        except ValueError:
            return False

    def get_all_ips(self) -> List[Dict]:
        """
        获取所有白名单记录

        Returns:
            List[Dict]: 白名单列表
        """
        if self.use_db:
            return whitelist_dao.get_all()
        else:
            # 从配置返回
            return [{'ip_or_cidr': ip, 'description': 'from config', 'type': 'config'}
                    for ip in Config.IP_WHITELIST]

    def get_stats(self) -> dict:
        """
        获取白名单统计信息

        Returns:
            dict: 统计信息
        """
        if self.use_db:
            return whitelist_dao.get_stats()
        else:
            return {
                'total': len(Config.IP_WHITELIST),
                'by_type': {'config': len(Config.IP_WHITELIST)}
            }

    def import_from_config(self) -> Dict:
        """
        从配置文件导入白名单到数据库

        Returns:
            Dict: 导入结果
        """
        if not self.use_db:
            return {'success': False, 'message': '数据库未启用'}

        imported = 0
        skipped = 0
        errors = []

        for ip in Config.IP_WHITELIST:
            ip = ip.strip()
            if not ip:
                continue
            try:
                if '/' in ip:
                    ipaddress.ip_network(ip, strict=False)
                else:
                    ipaddress.ip_address(ip)

                if whitelist_dao.add(ip, '从配置文件导入', 'config', 'system'):
                    imported += 1
                else:
                    skipped += 1
            except ValueError as e:
                errors.append({'ip': ip, 'error': str(e)})

        self._build_cache()
        return {
            'success': True,
            'imported': imported,
            'skipped': skipped,
            'errors': errors
        }


# 全局白名单管理器实例
whitelist_manager = WhitelistManager()


if __name__ == "__main__":
    # 测试代码
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description='白名单管理工具')
    parser.add_argument('action', choices=['add', 'remove', 'check', 'list', 'import', 'stats'], help='操作类型')
    parser.add_argument('--ip', help='IP地址或网段')
    parser.add_argument('--desc', help='描述')
    args = parser.parse_args()

    if args.action == 'add' and args.ip:
        result = whitelist_manager.add_ip(args.ip, args.desc or '手动添加')
        print(result['message'])

    elif args.action == 'remove' and args.ip:
        result = whitelist_manager.remove_ip(args.ip)
        print(result['message'])

    elif args.action == 'check' and args.ip:
        is_whitelisted = whitelist_manager.is_whitelisted(args.ip)
        print(f"{args.ip} {'在' if is_whitelisted else '不在'}白名单中")

    elif args.action == 'list':
        entries = whitelist_manager.get_all_ips()
        print(f"白名单共 {len(entries)} 条:")
        for entry in entries:
            print(f"  - {entry.get('ip_or_cidr')} ({entry.get('description', 'N/A')})")

    elif args.action == 'import':
        result = whitelist_manager.import_from_config()
        print(f"导入完成: 新增 {result['imported']} 条, 跳过 {result['skipped']} 条")
        if result['errors']:
            print(f"错误: {result['errors']}")

    elif args.action == 'stats':
        stats = whitelist_manager.get_stats()
        print(f"白名单统计: 总数 {stats['total']}")
        print(f"按类型分布: {stats['by_type']}")
