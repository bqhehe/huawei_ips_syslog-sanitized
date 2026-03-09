#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
告警去重模块
防止短时间内相同告警重复通知
"""

import sys
import os
import time
import logging
import hashlib
from typing import Dict, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import threading

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config

logger = logging.getLogger(__name__)


class AlertDeduplicator:
    """告警去重器"""

    def __init__(self, dedup_window: int = 300):
        """
        初始化告警去重器

        Args:
            dedup_window: 去重时间窗口（秒），默认5分钟
        """
        self.dedup_window = dedup_window
        self.alert_history: Dict[str, float] = {}
        self.lock = threading.Lock()

    def _generate_alert_key(self, src_ip: str, dst_ip: str, attack_type: str) -> str:
        """
        生成告警唯一标识

        Args:
            src_ip: 源IP
            dst_ip: 目标IP
            attack_type: 攻击类型

        Returns:
            str: 唯一标识
        """
        # 使用MD5生成唯一标识
        key_str = f"{src_ip}:{dst_ip}:{attack_type}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def should_alert(self, src_ip: str, dst_ip: str, attack_type: str) -> bool:
        """
        判断是否应该发送告警

        Args:
            src_ip: 源IP
            dst_ip: 目标IP
            attack_type: 攻击类型

        Returns:
            bool: 是否应该发送告警
        """
        key = self._generate_alert_key(src_ip, dst_ip, attack_type)
        now = time.time()

        with self.lock:
            # 检查是否在去重窗口内
            if key in self.alert_history:
                last_alert_time = self.alert_history[key]
                if now - last_alert_time < self.dedup_window:
                    logger.debug(f"告警去重: {src_ip} -> {dst_ip} ({attack_type}) 在去重窗口内")
                    return False

            # 更新告警时间
            self.alert_history[key] = now

            # 清理过期的告警记录
            self._cleanup_expired_alerts()

            return True

    def _cleanup_expired_alerts(self):
        """清理过期的告警记录"""
        now = time.time()
        expired_keys = []

        for key, alert_time in self.alert_history.items():
            if now - alert_time > self.dedup_window:
                expired_keys.append(key)

        for key in expired_keys:
            del self.alert_history[key]

        if expired_keys:
            logger.debug(f"清理了 {len(expired_keys)} 条过期告警记录")

    def get_alert_count(self, src_ip: str = None) -> int:
        """
        获取告警数量

        Args:
            src_ip: 源IP（可选），如果指定则返回该IP的告警数量

        Returns:
            int: 告警数量
        """
        with self.lock:
            if src_ip:
                # 返回指定IP的告警数量
                count = sum(1 for key in self.alert_history.keys() if src_ip in key)
                return count
            else:
                # 返回总告警数量
                return len(self.alert_history)

    def clear_history(self):
        """清空告警历史"""
        with self.lock:
            self.alert_history.clear()
            logger.info("告警历史已清空")


# 全局告警去重器实例
alert_deduplicator = AlertDeduplicator(dedup_window=300)


if __name__ == "__main__":
    # 测试代码
    import argparse

    parser = argparse.ArgumentParser(description='告警去重测试工具')
    parser.add_argument('action', choices=['test', 'count', 'clear'], help='操作类型')
    parser.add_argument('--src-ip', help='源IP')
    parser.add_argument('--dst-ip', help='目标IP')
    parser.add_argument('--attack-type', default='test', help='攻击类型')
    args = parser.parse_args()

    if args.action == 'test':
        if args.src_ip and args.dst_ip:
            for i in range(5):
                result = alert_deduplicator.should_alert(
                    args.src_ip,
                    args.dst_ip,
                    args.attack_type
                )
                print(f"测试 {i+1}: {'应该告警' if result else '跳过告警'}")
                time.sleep(1)
        else:
            print("请指定 --src-ip 和 --dst-ip")

    elif args.action == 'count':
        if args.src_ip:
            count = alert_deduplicator.get_alert_count(args.src_ip)
            print(f"IP {args.src_ip} 的告警数量: {count}")
        else:
            count = alert_deduplicator.get_alert_count()
            print(f"总告警数量: {count}")

    elif args.action == 'clear':
        alert_deduplicator.clear_history()
        print("告警历史已清空")