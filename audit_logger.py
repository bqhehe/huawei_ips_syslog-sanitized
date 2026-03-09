#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
审计日志模块（数据库版本）
记录所有防御操作的审计日志
"""

import sys
import os
import json
import logging
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from database.dao import audit_dao

logger = logging.getLogger(__name__)


class AuditLogger:
    """审计日志记录器（数据库版本）"""

    def __init__(self, use_db: bool = True):
        """
        初始化审计日志记录器

        Args:
            use_db: 是否使用数据库（默认True）
        """
        self.use_db = use_db
        # 保留文件模式作为备份
        self.audit_file = os.path.join(
            os.path.dirname(Config.LOG_FILE),
            'audit.log'
        )
        self._ensure_file_exists()
        logger.info("审计日志记录器初始化完成（使用数据库存储）")

    def _ensure_file_exists(self):
        """确保审计日志文件存在（备份用）"""
        audit_dir = os.path.dirname(self.audit_file)
        if audit_dir and not os.path.exists(audit_dir):
            os.makedirs(audit_dir, exist_ok=True)

        if not os.path.exists(self.audit_file):
            with open(self.audit_file, 'w', encoding='utf-8') as f:
                f.write('')

    def log(self, event_type: str, ip: str = None, details: Optional[Dict] = None) -> bool:
        """
        记录审计日志

        Args:
            event_type: 事件类型（block, unblock, alert等）
            ip: IP地址
            details: 详细信息
        """
        # 写入数据库
        if self.use_db:
            try:
                audit_dao.log(event_type, ip, details)
            except Exception as e:
                logger.error(f"数据库写入审计日志失败: {e}")

        # 同时写入文件作为备份
        try:
            audit_record = {
                'timestamp': datetime.now().isoformat(),
                'event_type': event_type,
                'ip': ip or 'N/A',
                'details': details or {}
            }

            with open(self.audit_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(audit_record, ensure_ascii=False) + '\n')

        except Exception as e:
            logger.error(f"写入审计日志文件失败: {e}")

        return True

    def log_block(self, ip: str, dst_ip: str, attack_type: str, severity: str):
        """
        记录封禁操作
        """
        return self.log('block', ip, {
            'dst_ip': dst_ip,
            'attack_type': attack_type,
            'severity': severity
        })

    def log_unblock(self, ip: str, reason: str = 'manual'):
        """
        记录解封操作
        """
        return self.log('unblock', ip, {
            'reason': reason
        })

    def log_alert(self, ip: str, dst_ip: str, attack_type: str, severity: str):
        """
        记录告警操作
        """
        return self.log('alert', ip, {
            'dst_ip': dst_ip,
            'attack_type': attack_type,
            'severity': severity
        })

    def log_error(self, event_type: str, ip: str, error: str):
        """
        记录错误操作
        """
        return self.log('error', ip, {
            'error': error
        })

    def get_recent_logs(self, count: int = 100) -> list:
        """
        获取最近的审计日志

        Args:
            count: 返回的日志数量

        Returns:
            list: 审计日志列表
        """
        if self.use_db:
            try:
                return audit_dao.get_recent_logs(count)
            except Exception as e:
                logger.error(f"从数据库获取审计日志失败: {e}")
                # 回退到文件读取
                pass

        # 回退到文件读取
        try:
            with open(self.audit_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 获取最近的记录
            recent_lines = lines[-count:] if len(lines) > count else lines

            # 解析JSON
            logs = []
            for line in recent_lines:
                try:
                    log = json.loads(line.strip())
                    logs.append(log)
                except json.JSONDecodeError:
                    continue

            return logs[::-1]  # 反转，最新的在前

        except Exception as e:
            logger.error(f"读取审计日志文件失败: {e}")
            return []


# 全局审计日志记录器实例
audit_logger = AuditLogger()


if __name__ == "__main__":
    # 测试代码
    import argparse

    parser = argparse.ArgumentParser(description='审计日志工具')
    parser.add_argument('action', choices=['view', 'block', 'unblock'], help='操作类型')
    parser.add_argument('--ip', help='IP地址')
    parser.add_argument('--count', type=int, default=100, help='查看的日志数量')
    args = parser.parse_args()

    if args.action == 'view':
        logs = audit_logger.get_recent_logs(args.count)
        print(f"最近的 {len(logs)} 条审计日志:")
        print("-" * 80)
        for log in logs:
            print(f"{log['timestamp']} - {log['event_type']} - {log['ip']}")
            if log.get('details'):
                print(f"  详情: {json.dumps(log['details'], ensure_ascii=False)}")
            print()

    elif args.action == 'block' and args.ip:
        audit_logger.log_block(args.ip, '10.0.0.1', 'test_attack', 'high')
        print(f"已记录封禁操作: {args.ip}")

    elif args.action == 'unblock' and args.ip:
        audit_logger.log_unblock(args.ip, 'manual')
        print(f"已记录解封操作: {args.ip}")
