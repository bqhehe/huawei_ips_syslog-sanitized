#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
分析引擎模块
提供威胁分析、趋势分析、关联分析等功能
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
from dataclasses import dataclass
import json

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.dao import alert_dao, blacklist_dao
from database.db import get_db

logger = logging.getLogger(__name__)


@dataclass
class ThreatScore:
    """威胁评分"""
    score: int  # 0-100
    level: str  # critical, high, medium, low, info
    factors: Dict[str, Any]
    timestamp: str


class AnalysisEngine:
    """分析引擎"""

    # 威胁评分权重配置
    SEVERITY_WEIGHTS = {
        'critical': 40,
        'high': 30,
        'medium': 20,
        'low': 10,
        'info': 5
    }

    # 高风险端口列表
    HIGH_RISK_PORTS = {
        22: 'SSH', 23: 'Telnet', 135: 'RPC', 139: 'NetBIOS',
        445: 'SMB', 1433: 'MSSQL', 1434: 'MSSQL', 3306: 'MySQL',
        3389: 'RDP', 5432: 'PostgreSQL', 5900: 'VNC', 6379: 'Redis',
        27017: 'MongoDB', 27018: 'MongoDB'
    }

    # 高风险攻击类型关键词
    HIGH_RISK_ATTACKS = [
        'mining', 'malware', 'trojan', 'botnet', 'ransomware',
        'exploit', 'cve', 'sql injection', 'xss', 'csrf', 'brute force',
        'ddos', 'backdoor', 'shell', 'injection', 'buffer overflow'
    ]

    def __init__(self):
        self.db = get_db()

    def get_trend_analysis(self, hours: int = 24, interval: int = 1) -> Dict:
        """
        获取趋势分析数据

        Args:
            hours: 分析时间范围（小时）
            interval: 时间间隔（小时）

        Returns:
            Dict: 趋势分析数据
        """
        try:
            with self.db.get_connection() as conn:
                # 按时间间隔统计告警数量
                time_buckets = []
                for i in range(hours // interval):
                    start_time = f"-{hours - i * interval} hours"
                    end_time = f"-{hours - (i + 1) * interval} hours"

                    count = conn.execute('''
                        SELECT COUNT(*) FROM alerts
                        WHERE timestamp >= datetime('now', ?)
                          AND timestamp < datetime('now', ?)
                    ''', (start_time, end_time)).fetchone()[0]

                    time_buckets.append({
                        'time': (datetime.now() - timedelta(hours=hours - i * interval)).strftime('%Y-%m-%d %H:00'),
                        'count': count
                    })

                # 按严重性统计趋势
                severity_trend = {}
                for severity in ['critical', 'high', 'medium', 'low', 'info']:
                    counts = []
                    for i in range(hours // interval):
                        start_time = f"-{hours - i * interval} hours"
                        end_time = f"-{hours - (i + 1) * interval} hours"

                        count = conn.execute('''
                            SELECT COUNT(*) FROM alerts
                            WHERE timestamp >= datetime('now', ?)
                              AND timestamp < datetime('now', ?)
                              AND severity = ?
                        ''', (start_time, end_time, severity)).fetchone()[0]
                        counts.append(count)

                    severity_trend[severity] = counts

                return {
                    'time_buckets': time_buckets,
                    'severity_trend': severity_trend,
                    'total_alerts': sum(b['count'] for b in time_buckets),
                    'peak_time': max(time_buckets, key=lambda x: x['count'])['time'] if time_buckets else None
                }
        except Exception as e:
            logger.error(f"获取趋势分析失败: {e}")
            return {'time_buckets': [], 'severity_trend': {}, 'total_alerts': 0, 'peak_time': None}

    def get_attack_type_distribution(self, hours: int = 24) -> Dict:
        """
        获取攻击类型分布

        Args:
            hours: 分析时间范围（小时）

        Returns:
            Dict: 攻击类型分布数据
        """
        try:
            with self.db.get_connection() as conn:
                # 按攻击类型统计
                results = conn.execute('''
                    SELECT attack_type, severity, COUNT(*) as count
                    FROM alerts
                    WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                    GROUP BY attack_type, severity
                    ORDER BY count DESC
                ''', (hours,)).fetchall()

                # 聚合数据
                attack_distribution = defaultdict(lambda: {'total': 0, 'by_severity': defaultdict(int)})
                for attack_type, severity, count in results:
                    attack_distribution[attack_type]['total'] += count
                    attack_distribution[attack_type]['by_severity'][severity] += count

                # 转换为列表并排序
                distribution = [
                    {
                        'attack_type': attack_type,
                        'total': data['total'],
                        'by_severity': dict(data['by_severity']),
                        'percentage': 0  # 稍后计算
                    }
                    for attack_type, data in attack_distribution.items()
                ]
                distribution.sort(key=lambda x: x['total'], reverse=True)

                # 计算百分比
                total_count = sum(d['total'] for d in distribution)
                for d in distribution:
                    d['percentage'] = round(d['total'] / total_count * 100, 2) if total_count > 0 else 0

                # 取TOP 10
                top_10 = distribution[:10]
                other_count = sum(d['total'] for d in distribution[10:])
                if other_count > 0:
                    top_10.append({
                        'attack_type': '其他',
                        'total': other_count,
                        'by_severity': {},
                        'percentage': round(other_count / total_count * 100, 2) if total_count > 0 else 0
                    })

                return {
                    'distribution': top_10,
                    'total_types': len(distribution),
                    'total_attacks': total_count
                }
        except Exception as e:
            logger.error(f"获取攻击类型分布失败: {e}")
            return {'distribution': [], 'total_types': 0, 'total_attacks': 0}

    def get_top_attackers(self, hours: int = 24, limit: int = 20) -> List[Dict]:
        """
        获取TOP攻击源

        Args:
            hours: 分析时间范围（小时）
            limit: 返回数量限制

        Returns:
            List[Dict]: TOP攻击源列表
        """
        try:
            # 导入IP地理位置查询模块
            try:
                from ip_geo_locator import ip_geo_locator
                geo_available = True
            except ImportError:
                geo_available = False

            with self.db.get_connection() as conn:
                # SQLite需要使用子查询来处理COUNT(DISTINCT)
                results = conn.execute('''
                    SELECT
                        src_ip,
                        COUNT(*) as attack_count,
                        (SELECT COUNT(DISTINCT dst_ip) FROM alerts a2 WHERE a2.src_ip = a1.src_ip
                         AND a2.timestamp >= datetime('now', '-' || ? || ' hours')) as target_count,
                        (SELECT COUNT(DISTINCT attack_type) FROM alerts a3 WHERE a3.src_ip = a1.src_ip
                         AND a3.timestamp >= datetime('now', '-' || ? || ' hours')) as variety_count,
                        MAX(severity) as max_severity,
                        SUBSTRING(GROUP_CONCAT(DISTINCT attack_type), 1, 200) as attack_types
                    FROM alerts a1
                    WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                    GROUP BY src_ip
                    ORDER BY attack_count DESC
                    LIMIT ?
                ''', (hours, hours, hours, limit)).fetchall()

                attackers = []
                for row in results:
                    # 计算威胁评分
                    threat_score = self._calculate_threat_score(
                        row['attack_count'],
                        row['target_count'],
                        row['variety_count'],
                        row['max_severity'],
                        row['attack_types']
                    )

                    # 查询IP地理位置信息
                    geo_info = {}
                    if geo_available:
                        try:
                            geo_info = ip_geo_locator.lookup(row['src_ip'])
                        except Exception as e:
                            logger.debug(f"查询IP地理位置失败 ({row['src_ip']}): {e}")

                    attackers.append({
                        'src_ip': row['src_ip'],
                        'attack_count': row['attack_count'],
                        'target_count': row['target_count'],
                        'variety_count': row['variety_count'],
                        'max_severity': row['max_severity'],
                        'attack_types': row['attack_types'][:100] if row['attack_types'] else '',
                        'threat_score': threat_score.score,
                        'threat_level': threat_score.level,
                        # 地理位置信息
                        'geo_country_code': geo_info.get('country_code'),
                        'geo_country_name': geo_info.get('country_name'),
                        'geo_country_flag': geo_info.get('country_flag'),
                        'geo_city': geo_info.get('city'),
                        'geo_display': f"{geo_info.get('country_flag', '🌍')} {geo_info.get('country_name', '未知')}" +
                                      (f" {geo_info.get('city')}" if geo_info.get('city') else '')
                    })

                return attackers
        except Exception as e:
            logger.error(f"获取TOP攻击源失败: {e}")
            return []

    def get_top_targets(self, hours: int = 24, limit: int = 20) -> List[Dict]:
        """
        获取TOP被攻击目标

        Args:
            hours: 分析时间范围（小时）
            limit: 返回数量限制

        Returns:
            List[Dict]: TOP被攻击目标列表
        """
        try:
            with self.db.get_connection() as conn:
                results = conn.execute('''
                    SELECT
                        dst_ip,
                        dst_port,
                        COALESCE(protocol, 'TCP') as protocol,
                        COUNT(*) as attack_count,
                        (SELECT COUNT(DISTINCT src_ip) FROM alerts a2
                         WHERE a2.dst_ip = a1.dst_ip AND a2.dst_port = a1.dst_port
                         AND a2.timestamp >= datetime('now', '-' || ? || ' hours')) as attacker_count,
                        (SELECT COUNT(DISTINCT attack_type) FROM alerts a3
                         WHERE a3.dst_ip = a1.dst_ip AND a3.dst_port = a1.dst_port
                         AND a3.timestamp >= datetime('now', '-' || ? || ' hours')) as variety_count,
                        MAX(severity) as max_severity
                    FROM alerts a1
                    WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                    GROUP BY dst_ip, dst_port, protocol
                    ORDER BY attack_count DESC
                    LIMIT ?
                ''', (hours, hours, hours, limit)).fetchall()

                targets = []
                for row in results:
                    # 判断端口风险
                    dst_port = row['dst_port'] or 0
                    port_risk = 'high' if dst_port in self.HIGH_RISK_PORTS else 'normal'

                    targets.append({
                        'dst_ip': row['dst_ip'],
                        'dst_port': dst_port,
                        'protocol': row['protocol'],
                        'service': self.HIGH_RISK_PORTS.get(dst_port, 'Unknown'),
                        'attack_count': row['attack_count'],
                        'attacker_count': row['attacker_count'],
                        'variety_count': row['variety_count'],
                        'max_severity': row['max_severity'],
                        'port_risk': port_risk
                    })

                return targets
        except Exception as e:
            logger.error(f"获取TOP被攻击目标失败: {e}")
            return []

    def get_time_distribution(self, hours: int = 24) -> Dict:
        """
        获取攻击时间分布

        Args:
            hours: 分析时间范围（小时）

        Returns:
            Dict: 时间分布数据
        """
        try:
            with self.db.get_connection() as conn:
                # 按小时统计
                hourly_data = []
                for i in range(24):
                    hour = (datetime.now() - timedelta(hours=23-i)).hour
                    count = conn.execute('''
                        SELECT COUNT(*) FROM alerts
                        WHERE timestamp >= datetime('now', '-24 hours')
                          AND CAST(strftime('%H', timestamp) AS INTEGER) = ?
                    ''', (hour,)).fetchone()[0]

                    hourly_data.append({
                        'hour': f"{hour:02d}:00",
                        'count': count
                    })

                # 按星期几统计
                weekday_data = []
                weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
                for i in range(7):
                    count = conn.execute('''
                        SELECT COUNT(*) FROM alerts
                        WHERE timestamp >= datetime('now', '-7 days')
                          AND CAST(strftime('%w', timestamp) AS INTEGER) = ?
                    ''', (i,)).fetchone()[0]

                    weekday_data.append({
                        'weekday': weekday_names[i],
                        'count': count
                    })

                return {
                    'hourly': hourly_data,
                    'weekday': weekday_data
                }
        except Exception as e:
            logger.error(f"获取时间分布失败: {e}")
            return {'hourly': [], 'weekday': []}

    def get_geo_distribution(self, hours: int = 24) -> Dict:
        """
        获取地理位置分布

        Args:
            hours: 分析时间范围（小时）

        Returns:
            Dict: 地理位置分布数据
        """
        try:
            with self.db.get_connection() as conn:
                # 按源IP统计（因为当前数据库结构没有geo字段）
                # 返回按攻击次数排序的IP分布
                results = conn.execute('''
                    SELECT
                        src_ip,
                        COUNT(*) as count
                    FROM alerts
                    WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                    GROUP BY src_ip
                    ORDER BY count DESC
                    LIMIT 15
                ''', (hours,)).fetchall()

                countries = []
                for row in results:
                    # 尝试获取IP的地理位置信息
                    try:
                        from ip_geo_locator import ip_geo_locator
                        geo_info = ip_geo_locator.lookup(row['src_ip'])
                        countries.append({
                            'country_name': geo_info.get('country_name', '未知'),
                            'country_code': geo_info.get('country_code', 'XX'),
                            'count': row['count'],
                            'unique_ips': 1
                        })
                    except:
                        countries.append({
                            'country_name': '未知',
                            'country_code': 'XX',
                            'count': row['count'],
                            'unique_ips': 1
                        })

                # 按国家聚合
                country_agg = {}
                for c in countries:
                    key = c['country_name']
                    if key not in country_agg:
                        country_agg[key] = {
                            'country_name': c['country_name'],
                            'country_code': c['country_code'],
                            'count': 0,
                            'unique_ips': 0
                        }
                    country_agg[key]['count'] += c['count']
                    country_agg[key]['unique_ips'] += c['unique_ips']

                # 转换为列表并排序
                sorted_countries = sorted(country_agg.values(), key=lambda x: x['count'], reverse=True)[:15]

                return {'countries': sorted_countries}
        except Exception as e:
            logger.error(f"获取地理位置分布失败: {e}")
            return {'countries': []}

    def get_correlation_analysis(self, hours: int = 24) -> Dict:
        """
        获取关联分析数据

        Args:
            hours: 分析时间范围（小时）

        Returns:
            Dict: 关联分析数据
        """
        try:
            with self.db.get_connection() as conn:
                # 横向关联：同一源IP攻击多目标
                multi_target_attackers = conn.execute('''
                    SELECT
                        src_ip,
                        (SELECT COUNT(DISTINCT dst_ip) FROM alerts a2
                         WHERE a2.src_ip = a1.src_ip
                         AND a2.timestamp >= datetime('now', '-' || ? || ' hours')) as target_count,
                        COUNT(*) as total_attacks
                    FROM alerts a1
                    WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                    GROUP BY src_ip
                    HAVING target_count >= 3
                    ORDER BY target_count DESC
                    LIMIT 10
                ''', (hours, hours)).fetchall()

                # 纵向关联：同一目标遭受多源攻击
                multi_source_targets = conn.execute('''
                    SELECT
                        dst_ip,
                        (SELECT COUNT(DISTINCT src_ip) FROM alerts a2
                         WHERE a2.dst_ip = a1.dst_ip
                         AND a2.timestamp >= datetime('now', '-' || ? || ' hours')) as attacker_count,
                        COUNT(*) as total_attacks
                    FROM alerts a1
                    WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                    GROUP BY dst_ip
                    HAVING attacker_count >= 3
                    ORDER BY attacker_count DESC
                    LIMIT 10
                ''', (hours, hours)).fetchall()

                # 协同攻击检测：短时间多IP攻击同一目标
                coordinated_attacks = conn.execute('''
                    SELECT
                        dst_ip,
                        (SELECT COUNT(DISTINCT src_ip) FROM alerts a2
                         WHERE a2.dst_ip = a1.dst_ip
                         AND a2.timestamp >= datetime('now', '-' || ? || ' hours')) as attacker_count,
                        MIN(timestamp) as first_seen,
                        MAX(timestamp) as last_seen,
                        COUNT(*) as total_attacks
                    FROM alerts a1
                    WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                    GROUP BY dst_ip
                    HAVING attacker_count >= 5
                    ORDER BY attacker_count DESC
                    LIMIT 10
                ''', (hours, hours)).fetchall()

                return {
                    'multi_target_attackers': [
                        {'src_ip': row['src_ip'], 'target_count': row['target_count'], 'total_attacks': row['total_attacks']}
                        for row in multi_target_attackers
                    ],
                    'multi_source_targets': [
                        {'dst_ip': row['dst_ip'], 'attacker_count': row['attacker_count'], 'total_attacks': row['total_attacks']}
                        for row in multi_source_targets
                    ],
                    'coordinated_attacks': [
                        {
                            'dst_ip': row['dst_ip'],
                            'attacker_count': row['attacker_count'],
                            'first_seen': row['first_seen'],
                            'last_seen': row['last_seen'],
                            'total_attacks': row['total_attacks']
                        }
                        for row in coordinated_attacks
                    ]
                }
        except Exception as e:
            logger.error(f"获取关联分析失败: {e}")
            return {'multi_target_attackers': [], 'multi_source_targets': [], 'coordinated_attacks': []}

    def get_overview_stats(self, hours: int = 24) -> Dict:
        """
        获取概览统计

        Args:
            hours: 分析时间范围（小时）

        Returns:
            Dict: 概览统计数据
        """
        try:
            with self.db.get_connection() as conn:
                # 总攻击数
                total_attacks = conn.execute('''
                    SELECT COUNT(*) FROM alerts
                    WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                ''', (hours,)).fetchone()[0]

                # 高危事件数
                high_risk_count = conn.execute('''
                    SELECT COUNT(*) FROM alerts
                    WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                      AND severity IN ('critical', 'high')
                ''', (hours,)).fetchone()[0]

                # 活跃攻击源数
                active_attackers = conn.execute('''
                    SELECT COUNT(DISTINCT src_ip) FROM alerts
                    WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                ''', (hours,)).fetchone()[0]

                # 被攻击资产数
                targeted_assets = conn.execute('''
                    SELECT COUNT(DISTINCT dst_ip) FROM alerts
                    WHERE timestamp >= datetime('now', '-' || ? || ' hours')
                ''', (hours,)).fetchone()[0]

                # 防护成功率（已封禁IP数 / 总攻击源数）
                blocked_ips = conn.execute('''
                    SELECT COUNT(DISTINCT src_ip) FROM blacklist
                    WHERE status = 'active'
                      AND added_at >= datetime('now', '-' || ? || ' hours')
                ''', (hours,)).fetchone()[0]

                protection_rate = round(blocked_ips / active_attackers * 100, 2) if active_attackers > 0 else 0

                return {
                    'total_attacks': total_attacks,
                    'high_risk_events': high_risk_count,
                    'active_attackers': active_attackers,
                    'targeted_assets': targeted_assets,
                    'protection_rate': protection_rate,
                    'blocked_ips': blocked_ips
                }
        except Exception as e:
            logger.error(f"获取概览统计失败: {e}")
            return {
                'total_attacks': 0,
                'high_risk_events': 0,
                'active_attackers': 0,
                'targeted_assets': 0,
                'protection_rate': 0,
                'blocked_ips': 0
            }

    def _calculate_threat_score(self, attack_count: int, target_count: int,
                               variety_count: int, max_severity: str,
                               attack_types: str) -> ThreatScore:
        """
        计算威胁评分

        Args:
            attack_count: 攻击次数
            target_count: 目标数量
            variety_count: 攻击类型多样性
            max_severity: 最大严重性
            attack_types: 攻击类型列表

        Returns:
            ThreatScore: 威胁评分
        """
        score = 0
        factors = {}

        # 1. 攻击次数得分 (0-25分)
        attack_score = min(attack_count * 2, 25)
        score += attack_score
        factors['attack_count'] = {'score': attack_score, 'value': attack_count}

        # 2. 目标数量得分 (0-20分)
        target_score = min(target_count * 5, 20)
        score += target_score
        factors['target_count'] = {'score': target_score, 'value': target_count}

        # 3. 攻击类型多样性得分 (0-15分)
        variety_score = min(variety_count * 3, 15)
        score += variety_score
        factors['variety'] = {'score': variety_score, 'value': variety_count}

        # 4. 严重性得分 (0-40分)
        severity_score = self.SEVERITY_WEIGHTS.get(max_severity.lower(), 20)
        score += severity_score
        factors['severity'] = {'score': severity_score, 'value': max_severity}

        # 5. 高风险攻击类型加分 (0-15分)
        high_risk_bonus = 0
        if attack_types:
            for keyword in self.HIGH_RISK_ATTACKS:
                if keyword in attack_types.lower():
                    high_risk_bonus += 3
            high_risk_bonus = min(high_risk_bonus, 15)
        score += high_risk_bonus
        factors['high_risk_bonus'] = {'score': high_risk_bonus, 'value': 'High risk patterns detected'}

        # 确定威胁等级
        if score >= 80:
            level = 'critical'
        elif score >= 60:
            level = 'high'
        elif score >= 40:
            level = 'medium'
        elif score >= 20:
            level = 'low'
        else:
            level = 'info'

        return ThreatScore(
            score=min(score, 100),
            level=level,
            factors=factors,
            timestamp=datetime.now().isoformat()
        )

    def generate_analysis_report(self, hours: int = 24) -> Dict:
        """
        生成完整分析报告

        Args:
            hours: 分析时间范围（小时）

        Returns:
            Dict: 完整分析报告
        """
        logger.info(f"生成分析报告，时间范围: {hours}小时")

        report = {
            'timestamp': datetime.now().isoformat(),
            'time_range': f'最近{hours}小时',
            'overview': self.get_overview_stats(hours),
            'trend': self.get_trend_analysis(hours),
            'attack_types': self.get_attack_type_distribution(hours),
            'top_attackers': self.get_top_attackers(hours),
            'top_targets': self.get_top_targets(hours),
            'time_distribution': self.get_time_distribution(hours),
            'geo_distribution': self.get_geo_distribution(hours),
            'correlation': self.get_correlation_analysis(hours)
        }

        logger.info(f"分析报告生成完成")
        return report


# 全局分析引擎实例
analysis_engine = AnalysisEngine()


if __name__ == "__main__":
    # 测试代码
    import argparse

    parser = argparse.ArgumentParser(description='分析引擎测试工具')
    parser.add_argument('--hours', type=int, default=24, help='分析时间范围（小时）')
    parser.add_argument('--output', help='输出文件路径（JSON格式）')
    args = parser.parse_args()

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 生成报告
    report = analysis_engine.generate_analysis_report(args.hours)

    # 输出结果
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"报告已保存到: {args.output}")
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
