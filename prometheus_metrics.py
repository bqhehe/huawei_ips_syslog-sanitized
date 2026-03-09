#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Prometheus指标导出模块
提供Prometheus格式的指标导出
"""

import sys
import os
import time
import logging
import threading
from typing import Dict, Counter
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from blacklist_manager import blacklist_manager

logger = logging.getLogger(__name__)

# 延迟导入数据库模块，避免循环导入
_alert_dao = None
def get_alert_dao():
    """延迟导入alert_dao"""
    global _alert_dao
    if _alert_dao is None:
        try:
            from database.dao import alert_dao
            _alert_dao = alert_dao
        except ImportError:
            logger.warning("数据库模块不可用，无法加载历史告警数据")
            _alert_dao = False
    return _alert_dao if _alert_dao is not False else None


class PrometheusMetrics:
    """Prometheus指标收集器"""

    def __init__(self):
        # 计数器
        self.logs_received_total = 0
        self.alerts_received_total = 0
        self.alerts_blocked_total = 0
        self.alerts_alerted_total = 0
        self.alerts_ignored_total = 0
        self.errors_total = 0

        # 按严重性分类的计数器
        self.alerts_by_severity: Dict[str, int] = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'info': 0
        }

        # 按攻击类型分类的计数器
        self.alerts_by_attack_type: Dict[str, int] = {}

        # 时间戳
        self.start_time = time.time()

        # 锁
        self.lock = threading.Lock()

        # 从数据库加载历史统计数据
        self._load_from_database()

    def _load_from_database(self):
        """从数据库加载历史告警统计数据"""
        alert_dao = get_alert_dao()
        if alert_dao is None:
            logger.info("无法从数据库加载历史告警数据")
            return

        try:
            stats = alert_dao.get_stats()

            with self.lock:
                # 更新总数
                self.alerts_received_total = stats.get('total', 0)

                # 更新按严重性分类的数据
                by_severity = stats.get('by_severity', {})
                for severity, count in by_severity.items():
                    severity_lower = severity.lower()
                    if severity_lower in self.alerts_by_severity:
                        self.alerts_by_severity[severity_lower] = count

                # 更新按攻击类型分类的数据
                by_attack_type = stats.get('by_attack_type', {})
                self.alerts_by_attack_type = dict(by_attack_type)

            logger.info(f"已从数据库加载历史告警数据: 总数={self.alerts_received_total}, "
                       f"严重性分布={self.alerts_by_severity}, "
                       f"攻击类型数量={len(self.alerts_by_attack_type)}")
        except Exception as e:
            logger.error(f"从数据库加载历史告警数据失败: {e}")

    def increment_log_received(self):
        """增加接收到的日志计数"""
        with self.lock:
            self.logs_received_total += 1

    def increment_alert_received(self, severity: str = 'unknown', attack_type: str = 'unknown'):
        """增加接收到的告警计数"""
        with self.lock:
            self.alerts_received_total += 1

            # 按严重性分类
            if severity.lower() in self.alerts_by_severity:
                self.alerts_by_severity[severity.lower()] += 1

            # 按攻击类型分类
            if attack_type not in self.alerts_by_attack_type:
                self.alerts_by_attack_type[attack_type] = 0
            self.alerts_by_attack_type[attack_type] += 1

    def increment_alert_blocked(self):
        """增加封禁的告警计数"""
        with self.lock:
            self.alerts_blocked_total += 1

    def increment_alert_alerted(self):
        """增加告警的计数"""
        with self.lock:
            self.alerts_alerted_total += 1

    def increment_alert_ignored(self):
        """增加忽略的告警计数"""
        with self.lock:
            self.alerts_ignored_total += 1

    def increment_error(self):
        """增加错误计数"""
        with self.lock:
            self.errors_total += 1

    def export_metrics(self) -> str:
        """导出Prometheus格式的指标"""
        lines = []

        # 基础信息
        lines.append(f'# HELP ips_syslog_logs_received_total Total number of logs received')
        lines.append(f'# TYPE ips_syslog_logs_received_total counter')
        lines.append(f'ips_syslog_logs_received_total {self.logs_received_total}')
        lines.append('')

        lines.append(f'# HELP ips_syslog_alerts_received_total Total number of alerts received')
        lines.append(f'# TYPE ips_syslog_alerts_received_total counter')
        lines.append(f'ips_syslog_alerts_received_total {self.alerts_received_total}')
        lines.append('')

        lines.append(f'# HELP ips_syslog_alerts_blocked_total Total number of alerts blocked')
        lines.append(f'# TYPE ips_syslog_alerts_blocked_total counter')
        lines.append(f'ips_syslog_alerts_blocked_total {self.alerts_blocked_total}')
        lines.append('')

        lines.append(f'# HELP ips_syslog_alerts_alerted_total Total number of alerts alerted')
        lines.append(f'# TYPE ips_syslog_alerts_alerted_total counter')
        lines.append(f'ips_syslog_alerts_alerted_total {self.alerts_alerted_total}')
        lines.append('')

        lines.append(f'# HELP ips_syslog_alerts_ignored_total Total number of alerts ignored')
        lines.append(f'# TYPE ips_syslog_alerts_ignored_total counter')
        lines.append(f'ips_syslog_alerts_ignored_total {self.alerts_ignored_total}')
        lines.append('')

        lines.append(f'# HELP ips_syslog_errors_total Total number of errors')
        lines.append(f'# TYPE ips_syslog_errors_total counter')
        lines.append(f'ips_syslog_errors_total {self.errors_total}')
        lines.append('')

        # 按严重性分类的指标
        lines.append(f'# HELP ips_syslog_alerts_by_severity Total number of alerts by severity')
        lines.append(f'# TYPE ips_syslog_alerts_by_severity gauge')
        for severity, count in self.alerts_by_severity.items():
            lines.append(f'ips_syslog_alerts_by_severity{{severity="{severity}"}} {count}')
        lines.append('')

        # 按攻击类型分类的指标
        lines.append(f'# HELP ips_syslog_alerts_by_attack_type Total number of alerts by attack type')
        lines.append(f'# TYPE ips_syslog_alerts_by_attack_type gauge')
        for attack_type, count in self.alerts_by_attack_type.items():
            lines.append(f'ips_syslog_alerts_by_attack_type{{attack_type="{attack_type}"}} {count}')
        lines.append('')

        # 黑名单统计
        stats = blacklist_manager.get_stats()
        lines.append(f'# HELP ips_syslog_blacklist_total Total number of IPs in blacklist')
        lines.append(f'# TYPE ips_syslog_blacklist_total gauge')
        lines.append(f'ips_syslog_blacklist_total {stats["total"]}')
        lines.append('')

        lines.append(f'# HELP ips_syslog_blacklist_active Number of active IPs in blacklist')
        lines.append(f'# TYPE ips_syslog_blacklist_active gauge')
        lines.append(f'ips_syslog_blacklist_active {stats["active"]}')
        lines.append('')

        lines.append(f'# HELP ips_syslog_blacklist_expired Number of expired IPs in blacklist')
        lines.append(f'# TYPE ips_syslog_blacklist_expired gauge')
        lines.append(f'ips_syslog_blacklist_expired {stats["expired"]}')
        lines.append('')

        lines.append(f'# HELP ips_syslog_blacklist_permanent Number of permanent IPs in blacklist')
        lines.append(f'# TYPE ips_syslog_blacklist_permanent gauge')
        lines.append(f'ips_syslog_blacklist_permanent {stats["permanent"]}')
        lines.append('')

        # 运行时间
        uptime = time.time() - self.start_time
        lines.append(f'# HELP ips_syslog_uptime_seconds Service uptime in seconds')
        lines.append(f'# TYPE ips_syslog_uptime_seconds gauge')
        lines.append(f'ips_syslog_uptime_seconds {uptime}')
        lines.append('')

        # 服务信息
        lines.append(f'# HELP ips_syslog_info Service information')
        lines.append(f'# TYPE ips_syslog_info gauge')
        lines.append(f'ips_syslog_info{{version="2.0.0",service="ips-syslog"}} 1')
        lines.append('')

        return '\n'.join(lines)

    def reset(self):
        """重置所有计数器"""
        with self.lock:
            self.logs_received_total = 0
            self.alerts_received_total = 0
            self.alerts_blocked_total = 0
            self.alerts_alerted_total = 0
            self.alerts_ignored_total = 0
            self.errors_total = 0
            self.alerts_by_severity = {k: 0 for k in self.alerts_by_severity}
            self.alerts_by_attack_type = {}


# 全局Prometheus指标实例
prometheus_metrics = PrometheusMetrics()


if __name__ == "__main__":
    # 测试代码
    metrics = PrometheusMetrics()

    # 模拟一些数据
    metrics.increment_alert_received('high', 'Brute Force')
    metrics.increment_alert_blocked()
    metrics.increment_alert_received('medium', 'Port Scan')
    metrics.increment_alert_ignored()
    metrics.increment_alert_received('critical', 'Mining Pool')
    metrics.increment_alert_blocked()
    metrics.increment_error()

    # 导出指标
    print(prometheus_metrics.export_metrics())
