#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据库模型模块
使用 SQLite 存储黑名单、审计日志、告警记录等数据
"""

import sqlite3
import logging
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
from contextlib import contextmanager

# 添加父目录到路径（数据库模块的父目录是项目根目录）
BASE_DIR = Path(__file__).parent.parent
logger = logging.getLogger(__name__)


class Database:
    """数据库管理类"""

    def __init__(self, db_path: str = None):
        """
        初始化数据库

        Args:
            db_path: 数据库文件路径
        """
        if db_path is None:
            db_path = BASE_DIR / 'data' / 'ips_system.db'

        self.db_path = db_path
        self._ensure_database_exists()
        self._init_tables()

    @contextmanager
    def get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_database_exists(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

    def _init_tables(self):
        """初始化数据库表"""
        with self.get_connection() as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            conn.execute('PRAGMA journal_mode = WAL')
            conn.execute('PRAGMA synchronous = NORMAL')

            # 黑名单表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS blacklist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip TEXT NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expire_at TIMESTAMP,
                    status TEXT DEFAULT 'active',
                    src_ip TEXT,
                    dst_ip TEXT,
                    attack_type TEXT,
                    severity TEXT,
                    rule_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建索引
            conn.execute('CREATE INDEX IF NOT EXISTS idx_blacklist_ip ON blacklist(ip)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_blacklist_status ON blacklist(status)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_blacklist_expire_at ON blacklist(expire_at)')

            # 审计日志表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    event_type TEXT NOT NULL,
                    ip TEXT,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建索引
            conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_logs(event_type)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_audit_ip ON audit_logs(ip)')

            # 告警记录表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    src_ip TEXT NOT NULL,
                    dst_ip TEXT NOT NULL,
                    src_port INTEGER,
                    dst_port INTEGER,
                    protocol TEXT,
                    attack_type TEXT,
                    severity TEXT,
                    action TEXT,
                    raw_log TEXT,
                    device TEXT,
                    detect_time TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建索引
            conn.execute('CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_alerts_src_ip ON alerts(src_ip)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity)')

            # 系统配置表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 白名单表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS whitelist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_or_cidr TEXT NOT NULL UNIQUE,
                    description TEXT,
                    type TEXT DEFAULT 'manual',
                    status TEXT DEFAULT 'active',
                    added_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建索引
            conn.execute('CREATE INDEX IF NOT EXISTS idx_whitelist_ip ON whitelist(ip_or_cidr)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_whitelist_status ON whitelist(status)')

            # 实时日志缓冲区表（可选，用于持久化日志缓冲）
            conn.execute('''
                CREATE TABLE IF NOT EXISTS log_buffer (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    log_type TEXT NOT NULL,
                    raw_data TEXT,
                    parsed_info TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('CREATE INDEX IF NOT EXISTS idx_log_buffer_type ON log_buffer(log_type)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_log_buffer_timestamp ON log_buffer(timestamp)')

            conn.commit()
            logger.info("数据库表初始化完成")

    def migrate_from_files(self):
        """从现有文件迁移数据到数据库"""
        logger.info("开始从文件迁移数据...")

        # 迁移黑名单
        self._migrate_blacklist()

        # 迁移审计日志
        self._migrate_audit_logs()

        # 迁移告警记录
        self._migrate_alerts()

        logger.info("数据迁移完成")

    def _migrate_blacklist(self):
        """迁移黑名单数据"""
        blacklist_file = BASE_DIR / 'data' / 'blacklist.json'
        if not blacklist_file.exists():
            logger.info("黑名单文件不存在，跳过迁移")
            return

        try:
            import json
            with open(blacklist_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            with self.get_connection() as conn:
                for ip, info in data.items():
                    try:
                        conn.execute('''
                            INSERT OR IGNORE INTO blacklist (ip, added_at, expire_at, status)
                            VALUES (?, ?, ?, ?)
                        ''', (ip, info.get('added_at'), info.get('expire_time'), info.get('status', 'active')))
                    except Exception as e:
                        logger.error(f"迁移黑名单IP {ip} 失败: {e}")

                conn.commit()
                migrated_count = len(data)
                logger.info(f"黑名单迁移完成: {migrated_count} 条记录")

            # 备份原文件
            backup_file = blacklist_file.with_suffix('.json.backup')
            os.rename(blacklist_file, backup_file)
            logger.info(f"原黑名单文件已备份到: {backup_file}")

        except Exception as e:
            logger.error(f"迁移黑名单失败: {e}")

    def _migrate_audit_logs(self):
        """迁移审计日志"""
        audit_file = BASE_DIR / 'logs' / 'audit.log'
        if not audit_file.exists():
            logger.info("审计日志文件不存在，跳过迁移")
            return

        try:
            migrated_count = 0
            with self.get_connection() as conn:
                with open(audit_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            log_entry = json.loads(line)
                            conn.execute('''
                                INSERT INTO audit_logs (timestamp, event_type, ip, details)
                                VALUES (?, ?, ?, ?)
                            ''', (
                                log_entry.get('timestamp'),
                                log_entry.get('event_type'),
                                log_entry.get('ip'),
                                json.dumps(log_entry.get('details', {}))
                            ))
                            migrated_count += 1
                        except json.JSONDecodeError:
                            continue

                conn.commit()
                logger.info(f"审计日志迁移完成: {migrated_count} 条记录")

            # 备份原文件
            backup_file = audit_file.with_suffix('.log.backup')
            os.rename(audit_file, backup_file)
            logger.info(f"原审计日志文件已备份到: {backup_file}")

        except Exception as e:
            logger.error(f"迁移审计日志失败: {e}")

    def _migrate_alerts(self):
        """迁移告警记录"""
        alerts_file = BASE_DIR / 'data' / 'Att.txt'
        if not alerts_file.exists():
            logger.info("告警记录文件不存在，跳过迁移")
            return

        # 告警记录格式复杂，暂时跳过迁移
        logger.info("告警记录迁移暂未实现（可后续添加）")


# 全局数据库实例
db = Database()


def get_db() -> Database:
    """获取数据库实例"""
    return db


if __name__ == '__main__':
    # 测试代码
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description='数据库管理工具')
    parser.add_argument('action', choices=['init', 'migrate', 'backup', 'query'], help='操作类型')
    parser.add_argument('--query', '-q', help='SQL查询语句')
    args = parser.parse_args()

    database = Database()

    if args.action == 'init':
        print("数据库初始化完成")

    elif args.action == 'migrate':
        confirm = input("确定要从文件迁移数据吗？将备份原文件 (yes/no): ")
        if confirm.lower() == 'yes':
            database.migrate_from_files()
        else:
            print("取消迁移")

    elif args.action == 'backup':
        import shutil
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = BASE_DIR / 'data' / f'ips_system_{timestamp}.db.backup'
        shutil.copy2(database.db_path, backup_path)
        print(f"数据库已备份到: {backup_path}")

    elif args.action == 'query':
        if not args.query:
            print("请提供SQL查询语句")
            sys.exit(1)

        with database.get_connection() as conn:
            cursor = conn.execute(args.query)
            rows = cursor.fetchall()
            if rows:
                print(f"查询结果 ({len(rows)} 行):")
                for row in rows:
                    print(dict(row))
            else:
                print("无结果")
