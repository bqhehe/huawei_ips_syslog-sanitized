#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据迁移脚本
将现有文件数据迁移到SQLite数据库
"""

import sys
import os
import logging
import argparse
from pathlib import Path

# 添加父目录到路径
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_blacklist():
    """迁移黑名单数据"""
    logger.info("开始迁移黑名单数据...")

    from database.dao import blacklist_dao
    import json

    blacklist_file = BASE_DIR / 'data' / 'blacklist.json'

    if not blacklist_file.exists():
        logger.info("黑名单文件不存在，跳过迁移")
        return 0

    try:
        with open(blacklist_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        migrated_count = 0
        for ip, info in data.items():
            try:
                # 计算过期时间
                expire_hours = 24  # 默认24小时
                if 'expire_time' in info and info['expire_time']:
                    try:
                        from datetime import datetime
                        expire_dt = datetime.fromisoformat(info['expire_time'])
                        remaining = expire_dt - datetime.now()
                        expire_hours = max(1, int(remaining.total_seconds() / 3600))
                    except:
                        pass

                # 添加到数据库
                if blacklist_dao.add(
                    ip=ip,
                    expire_hours=expire_hours,
                    src_ip=info.get('src_ip'),
                    dst_ip=info.get('dst_ip'),
                    attack_type=info.get('attack_type'),
                    severity=info.get('severity'),
                    rule_name=info.get('rule_name')
                ):
                    migrated_count += 1

            except Exception as e:
                logger.error(f"迁移黑名单IP {ip} 失败: {e}")

        logger.info(f"黑名单迁移完成: {migrated_count} 条记录")

        # 备份原文件
        if migrated_count > 0:
            backup_file = blacklist_file.with_suffix('.json.backup')
            if not backup_file.exists():
                import shutil
                shutil.copy2(blacklist_file, backup_file)
                logger.info(f"原黑名单文件已备份到: {backup_file}")

        return migrated_count

    except Exception as e:
        logger.error(f"迁移黑名单失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0


def migrate_audit_logs():
    """迁移审计日志"""
    logger.info("开始迁移审计日志...")

    from database.dao import audit_dao
    import json

    audit_file = BASE_DIR / 'logs' / 'audit.log'

    if not audit_file.exists():
        logger.info("审计日志文件不存在，跳过迁移")
        return 0

    try:
        migrated_count = 0
        with open(audit_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    log_entry = json.loads(line)

                    # 提取详细信息
                    event_type = log_entry.get('event_type')
                    ip = log_entry.get('ip')
                    details = log_entry.get('details', {})

                    # 调用对应的记录方法
                    if event_type == 'block':
                        audit_dao.log_block(
                            ip=ip,
                            dst_ip=details.get('dst_ip'),
                            attack_type=details.get('attack_type'),
                            severity=details.get('severity')
                        )
                    elif event_type == 'unblock':
                        audit_dao.log_unblock(
                            ip=ip,
                            reason=details.get('reason', 'manual')
                        )
                    elif event_type == 'alert':
                        audit_dao.log_alert(
                            ip=ip,
                            dst_ip=details.get('dst_ip'),
                            attack_type=details.get('attack_type'),
                            severity=details.get('severity')
                        )
                    elif event_type == 'error':
                        audit_dao.log_error(
                            event_type=details.get('error_type', 'error'),
                            ip=ip,
                            error=details.get('error')
                        )
                    else:
                        audit_dao.log(event_type, ip, details)

                    migrated_count += 1
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.error(f"迁移单条审计日志失败: {e}")

        logger.info(f"审计日志迁移完成: {migrated_count} 条记录")

        # 备份原文件
        if migrated_count > 0:
            backup_file = audit_file.with_suffix('.log.backup')
            if not backup_file.exists():
                import shutil
                shutil.copy2(audit_file, backup_file)
                logger.info(f"原审计日志文件已备份到: {backup_file}")

        return migrated_count

    except Exception as e:
        logger.error(f"迁移审计日志失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0


def migrate_alerts():
    """迁移告警记录"""
    logger.info("开始迁移告警记录...")

    from database.dao import alert_dao
    import re

    att_file = BASE_DIR / 'data' / 'Att.txt'

    if not att_file.exists():
        logger.info("告警记录文件不存在，跳过迁移")
        return 0

    try:
        with open(att_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 解析每条告警 - 支持 %%01IPS/4/DETECT 格式
        ips_pattern = re.compile(
            r'<\d+>(?:\w+\s+\d+\s+)?(\d{4}/?\d{2}/?\d{2}[^\s]*)\s+([^\s]+)\s+'
            r'%%01IPS/4/DETECT[^:]*:.*?\('
            r'(?:[^)]*?SrcIp=([\d.]+)[^,]*,\s*)?'
            r'(?:[^)]*?DstIp=([\d.]+)[^,]*,\s*)?'
            r'(?:[^)]*?SrcPort=(\d+)[^,]*,\s*)?'
            r'(?:[^)]*?DstPort=(\d+)[^,]*,\s*)?'
            r'(?:[^)]*?Protocol=(\w+)[^,]*,\s*)?'
            r'(?:[^)]*?SignName="([^"]+)"[^,]*,\s*)?'
            r'(?:[^)]*?Severity=(\w+)[^,]*,\s*)?'
            r'(?:[^)]*?Action=(\w+))?[^)]*\)'
        )

        # 解析 IPSTRAP 格式（兼容旧格式）
        ipstrap_pattern = re.compile(
            r'<\d+>(\w+\s+\d+\s+\d{4}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+'
            r'IPSTRAP/4/THREATTRAP:.*\s+\(SrcIp=([\d.]+),\s*DstIp=([\d.]+),\s*'
            r'SrcPort=(\d+),\s*DstPort=(\d+),\s*Protocol=(\w+),\s*Event=([^,]+),\s*DetectTime=([^)]+)\)'
        )

        migrated_count = 0

        # 先尝试解析 IPS 格式
        for match in ips_pattern.finditer(content):
            try:
                timestamp = match.group(1) if match.group(1) else match.group(2)
                device = match.group(2) if match.group(2) else "Firewall"
                src_ip = match.group(3) if match.group(3) else "N/A"
                dst_ip = match.group(4) if match.group(4) else "N/A"
                src_port = match.group(5) if match.group(5) else None
                dst_port = match.group(6) if match.group(6) else None
                protocol = match.group(7) if match.group(7) else "N/A"
                sign_name = match.group(8) if match.group(8) else "Unknown"
                severity = match.group(9) if match.group(9) else "medium"

                if alert_dao.add(
                    src_ip=src_ip,
                    dst_ip=dst_ip,
                    src_port=int(src_port) if src_port and src_port != 'N/A' else None,
                    dst_port=int(dst_port) if dst_port and dst_port != 'N/A' else None,
                    protocol=protocol,
                    attack_type=sign_name,
                    severity=severity.lower(),
                    action='block',
                    raw_log=match.group(0),
                    device=device,
                    detect_time=timestamp
                ):
                    migrated_count += 1
            except Exception as e:
                logger.debug(f"迁移单条告警失败: {e}")

        # 如果没有找到 IPS 格式，尝试解析 IPSTRAP 格式
        if migrated_count == 0:
            for match in ipstrap_pattern.finditer(content):
                try:
                    device = match.group(2)
                    src_ip = match.group(3)
                    dst_ip = match.group(4)
                    src_port = match.group(5)
                    dst_port = match.group(6)
                    protocol = match.group(7)
                    event = match.group(8).strip()
                    detect_time = match.group(9)

                    # 根据事件类型判断严重性
                    severity = 'medium'
                    event_lower = event.lower()
                    if any(kw in event_lower for kw in ['mining', 'malware', 'trojan', 'botnet', 'ransomware']):
                        severity = 'critical'
                    elif any(kw in event_lower for kw in ['brute force', 'injection', 'sql', 'xss', 'cve']):
                        severity = 'high'
                    elif any(kw in event_lower for kw in ['scan', 'probe', 'ddos']):
                        severity = 'medium'

                    if alert_dao.add(
                        src_ip=src_ip,
                        dst_ip=dst_ip,
                        src_port=int(src_port),
                        dst_port=int(dst_port),
                        protocol=protocol,
                        attack_type=event,
                        severity=severity,
                        action='block',
                        raw_log=match.group(0),
                        device=device,
                        detect_time=detect_time
                    ):
                        migrated_count += 1
                except Exception as e:
                    logger.debug(f"迁移单条告警失败: {e}")

        logger.info(f"告警记录迁移完成: {migrated_count} 条记录")

        return migrated_count

    except Exception as e:
        logger.error(f"迁移告警记录失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0


def show_stats():
    """显示数据库统计信息"""
    logger.info("=" * 50)
    logger.info("数据库统计信息")
    logger.info("=" * 50)

    try:
        from database.dao import blacklist_dao, audit_dao, alert_dao, log_buffer_dao

        # 黑名单统计
        blacklist_stats = blacklist_dao.get_stats()
        logger.info(f"黑名单总数: {blacklist_stats['total']}")
        logger.info(f"  - 活跃: {blacklist_stats['active']}")
        logger.info(f"  - 过期: {blacklist_stats['expired']}")
        logger.info(f"  - 永久: {blacklist_stats['permanent']}")

        # 审计日志统计
        audit_logs = audit_dao.get_recent_logs(10000)
        logger.info(f"审计日志总数: {len(audit_logs)}")

        # 告警统计
        alert_stats = alert_dao.get_stats()
        logger.info(f"告警记录总数: {alert_stats['total']}")
        logger.info(f"按严重性分布: {alert_stats['by_severity']}")
        logger.info(f"按攻击类型分布 (Top 10): {alert_stats['by_attack_type']}")

        # 日志缓冲统计
        log_stats = log_buffer_dao.get_stats()
        logger.info(f"日志缓冲总数: {log_stats['total']}")

    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")

    logger.info("=" * 50)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='数据迁移脚本')
    parser.add_argument('--all', action='store_true', help='迁移所有数据')
    parser.add_argument('--blacklist', action='store_true', help='迁移黑名单')
    parser.add_argument('--audit', action='store_true', help='迁移审计日志')
    parser.add_argument('--alerts', action='store_true', help='迁移告警记录')
    parser.add_argument('--stats', action='store_true', help='显示数据库统计')
    parser.add_argument('--confirm', action='store_true', help='确认执行迁移')

    args = parser.parse_args()

    # 如果没有指定任何选项，显示统计信息
    if not any([args.all, args.blacklist, args.audit, args.alerts, args.stats]):
        args.stats = True

    # 显示统计信息
    if args.stats:
        show_stats()
        return

    # 确认迁移
    if not args.confirm:
        logger.warning("请添加 --confirm 参数确认执行迁移操作")
        logger.warning("例如: python migrate_to_db.py --all --confirm")
        return

    # 执行迁移
    total_migrated = 0

    if args.all or args.blacklist:
        count = migrate_blacklist()
        total_migrated += count

    if args.all or args.audit:
        count = migrate_audit_logs()
        total_migrated += count

    if args.all or args.alerts:
        count = migrate_alerts()
        total_migrated += count

    logger.info(f"迁移完成，共迁移 {total_migrated} 条记录")

    # 显示迁移后统计
    logger.info("\n迁移后数据库统计:")
    show_stats()


if __name__ == '__main__':
    main()
