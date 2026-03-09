#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据访问层（DAO）
提供对数据库的增删改查操作
"""

import sqlite3
import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from contextlib import contextmanager

from .db import get_db

# 导入IP地理位置查询模块
try:
    from ip_geo_locator import ip_geo_locator
    GEOIP_AVAILABLE = True
except ImportError:
    GEOIP_AVAILABLE = False

logger = logging.getLogger(__name__)


class BlacklistDAO:
    """黑名单数据访问对象"""

    @staticmethod
    def add(ip: str, expire_hours: int = 24, src_ip: str = None, dst_ip: str = None,
             attack_type: str = None, severity: str = None, rule_name: str = None) -> bool:
        """添加IP到黑名单"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                expire_at = datetime.now() + timedelta(hours=expire_hours) if expire_hours > 0 else None

                conn.execute('''
                    INSERT OR REPLACE INTO blacklist (ip, expire_at, status, src_ip, dst_ip, attack_type, severity, rule_name)
                    VALUES (?, ?, 'active', ?, ?, ?, ?, ?)
                ''', (ip, expire_at, src_ip, dst_ip, attack_type, severity, rule_name))

                conn.commit()
                logger.debug(f"IP {ip} 已添加到黑名单数据库")
                return True
        except Exception as e:
            logger.error(f"添加黑名单失败: {e}")
            return False

    @staticmethod
    def remove(ip: str) -> bool:
        """从黑名单移除IP"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                conn.execute('DELETE FROM blacklist WHERE ip = ?', (ip,))
                conn.commit()
                logger.debug(f"IP {ip} 已从黑名单移除")
                return True
        except Exception as e:
            logger.error(f"移除黑名单失败: {e}")
            return False

    @staticmethod
    def get(ip: str) -> Optional[Dict]:
        """获取单个IP的黑名单信息"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM blacklist WHERE ip = ?
                ''', (ip,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"查询黑名单失败: {e}")
            return None

    @staticmethod
    def get_all() -> List[Dict]:
        """获取所有黑名单记录"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM blacklist WHERE status = 'active' ORDER BY added_at DESC
                ''')
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"获取黑名单列表失败: {e}")
            return []

    @staticmethod
    def get_stats() -> Dict[str, int]:
        """获取黑名单统计信息"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                # 总数
                total = conn.execute('SELECT COUNT(*) FROM blacklist WHERE status = "active"').fetchone()[0]

                # 活跃数量
                active = conn.execute('''
                    SELECT COUNT(*) FROM blacklist
                    WHERE status = 'active' AND (expire_at IS NULL OR expire_at > datetime('now'))
                ''').fetchone()[0]

                # 过期数量
                expired = conn.execute('''
                    SELECT COUNT(*) FROM blacklist
                    WHERE status = 'active' AND expire_at IS NOT NULL AND expire_at <= datetime('now')
                ''').fetchone()[0]

                # 永久数量
                permanent = conn.execute('''
                    SELECT COUNT(*) FROM blacklist
                    WHERE status = 'active' AND expire_at IS NULL
                ''').fetchone()[0]

                return {
                    'total': total,
                    'active': active,
                    'expired': expired,
                    'permanent': permanent
                }
        except Exception as e:
            logger.error(f"获取黑名单统计失败: {e}")
            return {'total': 0, 'active': 0, 'expired': 0, 'permanent': 0}

    @staticmethod
    def is_blocked(ip: str) -> bool:
        """检查IP是否在黑名单中"""
        info = BlacklistDAO.get(ip)
        if not info:
            return False

        # 检查状态和过期时间
        if info.get('status') != 'active':
            return False

        expire_at = info.get('expire_at')
        if expire_at:
            try:
                expire_dt = datetime.fromisoformat(expire_at)
                if expire_dt <= datetime.now():
                    # 已过期，更新状态
                    BlacklistDAO._update_status(ip, 'expired')
                    return False
            except:
                pass

        return True

    @staticmethod
    def _update_status(ip: str, status: str):
        """更新IP状态"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                conn.execute('UPDATE blacklist SET status = ? WHERE ip = ?', (status, ip))
                conn.commit()
        except Exception as e:
            logger.error(f"更新黑名单状态失败: {e}")

    @staticmethod
    def cleanup_expired() -> int:
        """清理过期的黑名单记录"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                cursor = conn.execute('''
                    UPDATE blacklist
                    SET status = 'expired'
                    WHERE status = 'active'
                      AND expire_at IS NOT NULL
                      AND expire_at <= datetime('now')
                ''')
                conn.commit()
                count = cursor.rowcount
                if count > 0:
                    logger.info(f"清理了 {count} 个过期的黑名单IP")
                return count
        except Exception as e:
            logger.error(f"清理过期黑名单失败: {e}")
            return 0


class AuditLogDAO:
    """审计日志数据访问对象"""

    @staticmethod
    def log(event_type: str, ip: str = None, details: Dict = None) -> bool:
        """记录审计日志"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                conn.execute('''
                    INSERT INTO audit_logs (event_type, ip, details)
                    VALUES (?, ?, ?)
                ''', (event_type, ip, json.dumps(details or {})))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"记录审计日志失败: {e}")
            return False

    @staticmethod
    def log_block(ip: str, dst_ip: str, attack_type: str, severity: str):
        """记录封禁操作"""
        AuditLogDAO.log('block', ip, {
            'dst_ip': dst_ip,
            'attack_type': attack_type,
            'severity': severity
        })

    @staticmethod
    def log_unblock(ip: str, reason: str = 'manual'):
        """记录解封操作"""
        AuditLogDAO.log('unblock', ip, {'reason': reason})

    @staticmethod
    def log_alert(ip: str, dst_ip: str, attack_type: str, severity: str):
        """记录告警操作"""
        AuditLogDAO.log('alert', ip, {
            'dst_ip': dst_ip,
            'attack_type': attack_type,
            'severity': severity
        })

    @staticmethod
    def log_error(event_type: str, ip: str, error: str):
        """记录错误操作"""
        AuditLogDAO.log('error', ip, {'error': error})

    @staticmethod
    def get_recent_logs(count: int = 100) -> List[Dict]:
        """获取最近的审计日志"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM audit_logs
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (count,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"获取审计日志失败: {e}")
            return []


class AlertDAO:
    """告警记录数据访问对象"""

    @staticmethod
    def add(src_ip: str, dst_ip: str, src_port: int, dst_port: int, protocol: str,
             attack_type: str, severity: str, action: str, raw_log: str, device: str = None,
             detect_time: str = None) -> bool:
        """添加告警记录"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                conn.execute('''
                    INSERT INTO alerts (src_ip, dst_ip, src_port, dst_port, protocol, attack_type,
                                    severity, action, raw_log, device, detect_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (src_ip, dst_ip, src_port, dst_port, protocol, attack_type,
                      severity, action, raw_log[:1000] if len(raw_log) > 1000 else raw_log,
                      device, detect_time))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"添加告警记录失败: {e}")
            return False

    @staticmethod
    def get_recent(count: int = 50) -> List[Dict]:
        """获取最近的告警记录"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM alerts
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (count,))
                rows = cursor.fetchall()
                alerts = [dict(row) for row in rows]

                # 为每个告警添加地理位置信息
                if GEOIP_AVAILABLE:
                    for alert in alerts:
                        src_ip = alert.get('src_ip')
                        if src_ip and src_ip != 'N/A':
                            try:
                                geo_info = ip_geo_locator.lookup(src_ip)
                                alert['geo_country_code'] = geo_info.get('country_code')
                                alert['geo_country_name'] = geo_info.get('country_name')
                                alert['geo_country_flag'] = geo_info.get('country_flag')
                                alert['geo_city'] = geo_info.get('city')
                                alert['geo_latitude'] = geo_info.get('latitude')
                                alert['geo_longitude'] = geo_info.get('longitude')
                                alert['geo_timezone'] = geo_info.get('timezone')
                                alert['geo_display'] = (
                                    f"{geo_info.get('country_flag', '🌍')} {geo_info.get('country_name', '未知')}" +
                                    (f"-{geo_info.get('city')}" if geo_info.get('city') else '')
                                )
                            except Exception as e:
                                logger.debug(f"查询IP地理位置失败 ({src_ip}): {e}")
                                alert['geo_display'] = '未知'

                return alerts
        except Exception as e:
            logger.error(f"获取告警记录失败: {e}")
            return []

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """获取告警统计"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                # 总数
                total = conn.execute('SELECT COUNT(*) FROM alerts').fetchone()[0]

                # 按严重性统计
                severity_stats = conn.execute('''
                    SELECT severity, COUNT(*) as count
                    FROM alerts
                    GROUP BY severity
                ''').fetchall()

                # 按攻击类型统计
                attack_stats = conn.execute('''
                    SELECT attack_type, COUNT(*) as count
                    FROM alerts
                    GROUP BY attack_type
                    ORDER BY count DESC
                    LIMIT 10
                ''').fetchall()

                return {
                    'total': total,
                    'by_severity': {row[0]: row[1] for row in severity_stats},
                    'by_attack_type': {row[0]: row[1] for row in attack_stats}
                }
        except Exception as e:
            logger.error(f"获取告警统计失败: {e}")
            return {'total': 0, 'by_severity': {}, 'by_attack_type': {}}

    @staticmethod
    def get_alert_stats() -> Dict[str, int]:
        """获取告警统计数据（总数、今日、本周、本月、高危）"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                # 总数
                total_count = conn.execute('SELECT COUNT(*) FROM alerts').fetchone()[0]

                # 今日告警（假设timestamp是UTC时间）
                today_count = conn.execute('''
                    SELECT COUNT(*) FROM alerts
                    WHERE date(timestamp) = date('now')
                ''').fetchone()[0]

                # 本周告警（最近7天）
                week_count = conn.execute('''
                    SELECT COUNT(*) FROM alerts
                    WHERE timestamp >= datetime('now', '-7 days')
                ''').fetchone()[0]

                # 本月告警（当月1日至今）
                month_count = conn.execute('''
                    SELECT COUNT(*) FROM alerts
                    WHERE timestamp >= datetime('now', 'start of month')
                ''').fetchone()[0]

                # 高危告警（critical和high级别）
                critical_count = conn.execute('''
                    SELECT COUNT(*) FROM alerts
                    WHERE severity IN ('critical', 'high')
                ''').fetchone()[0]

                return {
                    'total': total_count,
                    'today': today_count,
                    'week': week_count,
                    'month': month_count,
                    'critical': critical_count
                }
        except Exception as e:
            logger.error(f"获取告警统计失败: {e}")
            return {'total': 0, 'today': 0, 'week': 0, 'month': 0, 'critical': 0}


class LogBufferDAO:
    """日志缓冲区数据访问对象"""

    @staticmethod
    def add(log_type: str, raw_data: str, parsed_info: Dict = None) -> bool:
        """添加日志到缓冲区"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                conn.execute('''
                    INSERT INTO log_buffer (log_type, raw_data, parsed_info)
                    VALUES (?, ?, ?)
                ''', (log_type, raw_data[:1000] if len(raw_data) > 1000 else raw_data,
                      json.dumps(parsed_info or {})))
                conn.commit()

                # 保持固定大小（删除旧记录）
                conn.execute('''
                    DELETE FROM log_buffer
                    WHERE id NOT IN (
                        SELECT id FROM log_buffer
                        ORDER BY timestamp DESC
                        LIMIT 100
                    )
                ''')
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"添加日志缓冲失败: {e}")
            return False

    @staticmethod
    def get_recent(count: int = 100, log_type: str = None) -> List[Dict]:
        """获取最近的日志"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                if log_type:
                    cursor = conn.execute('''
                        SELECT * FROM log_buffer
                        WHERE log_type = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    ''', (log_type, count))
                else:
                    cursor = conn.execute('''
                        SELECT * FROM log_buffer
                        ORDER BY timestamp DESC
                        LIMIT ?
                    ''', (count,))

                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"获取日志缓冲失败: {e}")
            return []

    @staticmethod
    def get_stats() -> Dict:
        """获取日志统计"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                # 总数
                total = conn.execute('SELECT COUNT(*) FROM log_buffer').fetchone()[0]

                # 按类型统计
                type_stats = conn.execute('''
                    SELECT log_type, COUNT(*) as count
                    FROM log_buffer
                    GROUP BY log_type
                ''').fetchall()

                return {
                    'total': total,
                    'by_type': {row[0]: row[1] for row in type_stats},
                    'max_size': 100
                }
        except Exception as e:
            logger.error(f"获取日志统计失败: {e}")
            return {'total': 0, 'by_type': {}, 'max_size': 100}

    @staticmethod
    def clear_old_logs(days: int = 7):
        """清理旧日志"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                cursor = conn.execute('''
                    DELETE FROM log_buffer
                    WHERE timestamp < datetime('now', '-' || ? || ' days')
                ''', (days,))
                conn.commit()
                count = cursor.rowcount
                if count > 0:
                    logger.info(f"清理了 {count} 条旧日志记录")
                return count
        except Exception as e:
            logger.error(f"清理旧日志失败: {e}")
            return 0


class WhitelistDAO:
    """白名单数据访问对象"""

    @staticmethod
    def add(ip_or_cidr: str, description: str = None, type: str = 'manual', added_by: str = None) -> bool:
        """添加IP或网段到白名单"""
        db = get_db()
        try:
            # 验证IP格式
            import ipaddress
            try:
                if '/' in ip_or_cidr:
                    ipaddress.ip_network(ip_or_cidr, strict=False)
                else:
                    ipaddress.ip_address(ip_or_cidr)
            except ValueError:
                logger.error(f"无效的IP或网段格式: {ip_or_cidr}")
                return False

            with db.get_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO whitelist (ip_or_cidr, description, type, status, added_by)
                    VALUES (?, ?, ?, 'active', ?)
                ''', (ip_or_cidr.strip(), description, type, added_by))
                conn.commit()
                logger.debug(f"已添加到白名单: {ip_or_cidr}")
                return True
        except Exception as e:
            logger.error(f"添加白名单失败: {e}")
            return False

    @staticmethod
    def remove(ip_or_cidr: str) -> bool:
        """从白名单移除IP或网段"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                conn.execute('DELETE FROM whitelist WHERE ip_or_cidr = ?', (ip_or_cidr.strip(),))
                conn.commit()
                logger.debug(f"已从白名单移除: {ip_or_cidr}")
                return True
        except Exception as e:
            logger.error(f"移除白名单失败: {e}")
            return False

    @staticmethod
    def get_all() -> List[Dict]:
        """获取所有白名单记录"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM whitelist WHERE status = 'active' ORDER BY created_at DESC
                ''')
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"获取白名单列表失败: {e}")
            return []

    @staticmethod
    def is_whitelisted(ip: str) -> bool:
        """检查IP是否在白名单中（支持单个IP和CIDR网段）"""
        import ipaddress

        whitelist = WhitelistDAO.get_all()
        try:
            check_ip = ipaddress.ip_address(ip)
        except ValueError:
            return False

        for item in whitelist:
            try:
                entry = item['ip_or_cidr'].strip()
                if '/' in entry:
                    # 网段匹配
                    network = ipaddress.ip_network(entry, strict=False)
                    if check_ip in network:
                        return True
                else:
                    # 单个IP匹配
                    if str(check_ip) == entry:
                        return True
            except Exception:
                continue

        return False

    @staticmethod
    def get_stats() -> Dict:
        """获取白名单统计信息"""
        db = get_db()
        try:
            with db.get_connection() as conn:
                total = conn.execute('SELECT COUNT(*) FROM whitelist WHERE status = "active"').fetchone()[0]

                # 按类型统计
                type_stats = conn.execute('''
                    SELECT type, COUNT(*) as count
                    FROM whitelist
                    WHERE status = 'active'
                    GROUP BY type
                ''').fetchall()

                return {
                    'total': total,
                    'by_type': {row[0]: row[1] for row in type_stats}
                }
        except Exception as e:
            logger.error(f"获取白名单统计失败: {e}")
            return {'total': 0, 'by_type': {}}


# 快捷访问实例
blacklist_dao = BlacklistDAO()
audit_dao = AuditLogDAO()
alert_dao = AlertDAO()
log_buffer_dao = LogBufferDAO()
whitelist_dao = WhitelistDAO()
