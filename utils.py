#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
工具函数模块
提供异步处理、速率限制等工具函数
"""

import sys
import os
import time
import logging
import threading
from typing import Callable, Dict, Optional
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RateLimiter:
    """速率限制器"""

    def __init__(self, max_requests: int = 10, time_window: int = 60):
        """
        初始化速率限制器

        Args:
            max_requests: 时间窗口内最大请求数
            time_window: 时间窗口（秒）
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[str, list] = defaultdict(list)
        self.lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        """
        检查是否允许请求

        Args:
            key: 限制键（通常是IP地址）

        Returns:
            bool: 是否允许
        """
        with self.lock:
            now = time.time()

            # 清理过期的请求记录
            self.requests[key] = [
                req_time for req_time in self.requests[key]
                if now - req_time < self.time_window
            ]

            # 检查是否超过限制
            if len(self.requests[key]) >= self.max_requests:
                logger.warning(f"速率限制触发: {key} 超过限制")
                return False

            # 记录本次请求
            self.requests[key].append(now)
            return True

    def cleanup(self):
        """清理所有过期的请求记录"""
        with self.lock:
            now = time.time()
            for key in list(self.requests.keys()):
                self.requests[key] = [
                    req_time for req_time in self.requests[key]
                    if now - req_time < self.time_window
                ]
                if not self.requests[key]:
                    del self.requests[key]


class AsyncTaskRunner:
    """异步任务运行器"""

    def __init__(self, max_workers: int = 5):
        """
        初始化异步任务运行器

        Args:
            max_workers: 最大工作线程数
        """
        self.max_workers = max_workers
        self.workers: list = []
        self.lock = threading.Lock()

    def submit(self, func: Callable, *args, **kwargs):
        """
        提交异步任务

        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
        """
        def wrapper():
            try:
                func(*args, **kwargs)
            except Exception as e:
                logger.error(f"异步任务执行失败: {e}")
            finally:
                with self.lock:
                    if self.workers:
                        self.workers.remove(thread)

        # 清理已完成的线程
        with self.lock:
            self.workers = [t for t in self.workers if t.is_alive()]

            # 检查线程数限制
            if len(self.workers) >= self.max_workers:
                logger.warning(f"异步任务线程池已满，丢弃任务")
                return

            # 创建并启动线程
            thread = threading.Thread(target=wrapper, daemon=True)
            thread.start()
            self.workers.append(thread)

    def wait_all(self, timeout: Optional[float] = None):
        """
        等待所有任务完成

        Args:
            timeout: 超时时间（秒）
        """
        start_time = time.time()

        while True:
            with self.lock:
                active_workers = [t for t in self.workers if t.is_alive()]

            if not active_workers:
                break

            if timeout and (time.time() - start_time) > timeout:
                logger.warning("等待异步任务超时")
                break

            time.sleep(0.1)


def async_task(func: Callable):
    """
    异步任务装饰器

    Args:
        func: 要装饰的函数
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        def task():
            try:
                func(*args, **kwargs)
            except Exception as e:
                logger.error(f"异步任务执行失败: {e}")

        thread = threading.Thread(target=task, daemon=True)
        thread.start()

    return wrapper


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    重试装饰器

    Args:
        max_attempts: 最大尝试次数
        delay: 初始延迟（秒）
        backoff: 退避因子
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            current_delay = delay

            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts >= max_attempts:
                        logger.error(f"重试 {max_attempts} 次后仍然失败: {e}")
                        raise

                    logger.warning(f"操作失败，{current_delay}秒后重试 ({attempts}/{max_attempts}): {e}")
                    time.sleep(current_delay)
                    current_delay *= backoff

        return wrapper
    return decorator


def format_timestamp(timestamp: Optional[str] = None) -> str:
    """
    格式化时间戳

    Args:
        timestamp: ISO格式时间戳，None表示当前时间

    Returns:
        str: 格式化后的时间字符串
    """
    if timestamp:
        dt = datetime.fromisoformat(timestamp)
    else:
        dt = datetime.now()

    return dt.strftime('%Y-%m-%d %H:%M:%S')


def validate_ip(ip: str) -> bool:
    """
    验证IP地址格式

    Args:
        ip: IP地址字符串

    Returns:
        bool: 是否有效
    """
    import ipaddress
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


# 全局速率限制器实例
global_rate_limiter = RateLimiter(max_requests=100, time_window=60)

# 全局异步任务运行器
global_task_runner = AsyncTaskRunner(max_workers=10)


class LogBuffer:
    """日志环形缓冲区，用于保存最近的日志记录（数据库版本）"""

    def __init__(self, max_size: int = 100, use_db: bool = True):
        """
        初始化日志缓冲区

        Args:
            max_size: 最大保存日志数量
            use_db: 是否使用数据库存储（默认True）
        """
        self.max_size = max_size
        self.use_db = use_db
        self.logs: list = []  # 内存缓存，用于快速访问
        self.lock = threading.Lock()

        # 延迟导入数据库模块
        self._dao = None
        if use_db:
            try:
                from database.dao import log_buffer_dao
                self._dao = log_buffer_dao
            except ImportError:
                logger.warning("数据库模块不可用，使用内存存储")
                self.use_db = False

    def add(self, log_type: str, raw_data: str, parsed_info: dict = None):
        """
        添加日志到缓冲区

        Args:
            log_type: 日志类型 (IPS, SESSION, 等)
            raw_data: 原始日志数据
            parsed_info: 解析后的信息字典
        """
        with self.lock:
            import datetime

            log_entry = {
                'timestamp': datetime.datetime.now().isoformat(),
                'type': log_type,
                'raw': raw_data[:1000] if len(raw_data) > 1000 else raw_data,  # 限制长度
                'parsed': parsed_info or {}
            }

            # 添加到内存缓存
            self.logs.append(log_entry)
            if len(self.logs) > self.max_size:
                self.logs = self.logs[-self.max_size:]

            # 只将IPS告警日志写入数据库，SESSION等日志不持久化
            if self.use_db and self._dao and log_type == 'IPS':
                try:
                    self._dao.add(log_type, raw_data, parsed_info)
                except Exception as e:
                    logger.error(f"写入日志缓冲数据库失败: {e}")

    def get_recent(self, count: int = 100, log_type: str = None) -> list:
        """
        获取最近的日志

        Args:
            count: 返回的日志数量
            log_type: 过滤日志类型，None表示全部

        Returns:
            list: 日志列表（按时间倒序）
        """
        # 如果指定了日志类型
        if log_type:
            # IPS日志从数据库读取（有更多历史记录）
            if log_type == 'IPS' and self.use_db and self._dao:
                try:
                    db_logs = self._dao.get_recent(count, log_type)
                    # 转换数据库字段名到前端期望的格式
                    return self._convert_db_logs(db_logs)
                except Exception as e:
                    logger.error(f"从数据库读取IPS日志失败: {e}")
            # 其他类型日志从内存读取（SESSION、AM等不存数据库）
            with self.lock:
                filtered = [log for log in self.logs if log['type'] == log_type]
                return filtered[-count:][::-1]

        # 如果没有指定类型，返回所有日志
        # 从数据库获取所有类型的日志（IPS、SESSION等）
        if self.use_db and self._dao:
            try:
                db_logs = self._dao.get_recent(count, None)
                # 转换数据库字段名到前端期望的格式
                return self._convert_db_logs(db_logs)
            except Exception as e:
                logger.error(f"从数据库读取日志失败: {e}")

        # 回退到内存数据
        with self.lock:
            return self.logs[-count:][::-1]

    def _convert_db_logs(self, db_logs: list) -> list:
        """
        将数据库日志格式转换为前端期望的格式

        数据库字段: timestamp, log_type, raw_data, parsed_info
        前端期望: timestamp, type, raw, parsed
        """
        converted = []
        for log in db_logs:
            converted_log = {
                'timestamp': log.get('timestamp'),
                'type': log.get('log_type'),
                'raw': log.get('raw_data', ''),
            }
            # 解析 parsed_info JSON 字符串
            parsed_info = log.get('parsed_info')
            if parsed_info:
                try:
                    import json
                    converted_log['parsed'] = json.loads(parsed_info)
                except:
                    converted_log['parsed'] = {}
            else:
                converted_log['parsed'] = {}
            converted.append(converted_log)
        return converted

    def get_stats(self) -> dict:
        """
        获取日志统计信息

        Returns:
            dict: 统计信息
        """
        from collections import Counter

        # 合并数据库和内存的统计数据
        stats = {
            'total': 0,
            'by_type': {},
            'max_size': self.max_size
        }

        # 从数据库获取IPS日志统计
        if self.use_db and self._dao:
            try:
                db_stats = self._dao.get_stats()
                stats['total'] += db_stats.get('total', 0)
                stats['by_type'].update(db_stats.get('by_type', {}))
            except Exception as e:
                logger.error(f"从数据库获取日志统计失败: {e}")

        # 从内存获取非IPS日志统计
        with self.lock:
            non_ips_logs = [log for log in self.logs if log['type'] != 'IPS']
            stats['total'] += len(non_ips_logs)

            # 统计内存中各类型的日志数量
            for log in non_ips_logs:
                log_type = log['type']
                stats['by_type'][log_type] = stats['by_type'].get(log_type, 0) + 1

        return stats

    def clear(self):
        """清空缓冲区（仅清空内存缓存）"""
        with self.lock:
            self.logs.clear()

    def clear_old_logs(self, days: int = 7):
        """
        清理旧的日志记录

        Args:
            days: 保留天数，超过此天数的日志将被删除
        """
        if self.use_db and self._dao:
            try:
                return self._dao.clear_old_logs(days)
            except Exception as e:
                logger.error(f"清理旧日志失败: {e}")
        return 0


# 全局日志缓冲区实例
global_log_buffer = LogBuffer(max_size=100)


if __name__ == "__main__":
    # 测试代码
    import argparse

    parser = argparse.ArgumentParser(description='工具函数测试')
    parser.add_argument('test', choices=['rate_limiter', 'async_task', 'retry'], help='测试类型')
    args = parser.parse_args()

    if args.test == 'rate_limiter':
        limiter = RateLimiter(max_requests=3, time_window=5)
        for i in range(10):
            key = 'test_ip'
            if limiter.is_allowed(key):
                print(f"请求 {i+1}: 允许")
            else:
                print(f"请求 {i+1}: 拒绝")
            time.sleep(0.5)

    elif args.test == 'async_task':
        @async_task
        def test_task(name: str, delay: int):
            print(f"任务 {name} 开始")
            time.sleep(delay)
            print(f"任务 {name} 完成")

        for i in range(5):
            test_task(f"task_{i}", 1)

        print("主线程继续执行...")
        time.sleep(3)

    elif args.test == 'retry':
        @retry(max_attempts=3, delay=1)
        def test_retry():
            import random
            if random.random() > 0.3:
                raise Exception("随机失败")
            print("操作成功")

        test_retry()