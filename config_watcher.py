#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置文件热重载模块
监控配置文件变化并自动重新加载
"""

import os
import time
import logging
import threading
from typing import Callable, Dict, Set
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigWatcher:
    """配置文件监控器"""

    def __init__(self):
        """初始化配置监控器"""
        self.base_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        self.watched_files: Dict[str, float] = {}  # 文件路径 -> 最后修改时间
        self.callbacks: Dict[str, Set[Callable]] = {}  # 文件路径 -> 回调函数集合
        self.running = False
        self.thread = None
        self.check_interval = 5  # 检查间隔（秒）

        # 默认监控的文件
        self._init_default_files()

    def _init_default_files(self):
        """初始化默认监控文件"""
        default_files = [
            '.env',
            'data/notification_config.json',
            'data/notification_templates.json',
            'data/users.json',
        ]

        for file_path in default_files:
            full_path = self.base_dir / file_path
            if full_path.exists():
                self.watched_files[str(full_path)] = full_path.stat().st_mtime

    def add_file(self, file_path: str, callback: Callable = None):
        """
        添加文件监控

        Args:
            file_path: 文件路径（相对或绝对）
            callback: 文件变化时的回调函数
        """
        if not os.path.isabs(file_path):
            full_path = self.base_dir / file_path
        else:
            full_path = Path(file_path)

        if full_path.exists():
            self.watched_files[str(full_path)] = full_path.stat().st_mtime

            if callback:
                file_key = str(full_path)
                if file_key not in self.callbacks:
                    self.callbacks[file_key] = set()
                self.callbacks[file_key].add(callback)

            logger.info(f"已添加文件监控: {full_path}")
        else:
            logger.warning(f"文件不存在，无法添加监控: {full_path}")

    def remove_file(self, file_path: str):
        """移除文件监控"""
        if not os.path.isabs(file_path):
            full_path = str(self.base_dir / file_path)
        else:
            full_path = file_path

        if full_path in self.watched_files:
            del self.watched_files[full_path]

        if full_path in self.callbacks:
            del self.callbacks[full_path]

        logger.info(f"已移除文件监控: {full_path}")

    def _check_files(self):
        """检查文件变化"""
        changed_files = []

        for file_path, last_mtime in list(self.watched_files.items()):
            try:
                current_mtime = os.path.getmtime(file_path)
                if current_mtime > last_mtime:
                    self.watched_files[file_path] = current_mtime
                    changed_files.append(file_path)
            except FileNotFoundError:
                logger.warning(f"监控的文件不存在: {file_path}")

        return changed_files

    def _reload_configs(self, changed_files):
        """重新加载配置"""
        for file_path in changed_files:
            try:
                # 获取文件名（不含路径）用于判断类型
                file_name = os.path.basename(file_path)

                # 根据文件类型执行不同的重载逻辑
                if file_name == '.env':
                    self._reload_env()
                elif file_name == 'notification_config.json':
                    self._reload_notification_config()
                elif file_name == 'notification_templates.json':
                    self._reload_notification_templates()
                elif file_name == 'users.json':
                    self._reload_users()

                # 调用注册的回调函数
                if file_path in self.callbacks:
                    for callback in self.callbacks[file_path]:
                        try:
                            callback(file_path)
                        except Exception as e:
                            logger.error(f"回调函数执行失败: {e}")

                logger.info(f"已重新加载配置文件: {file_path}")

            except Exception as e:
                logger.error(f"重新加载配置失败 {file_path}: {e}")

    def _reload_env(self):
        """重新加载.env文件"""
        from config import load_env_file
        load_env_file()

    def _reload_notification_config(self):
        """重新加载通知配置"""
        from notification.notification_sender import notification_sender
        notification_sender.reload_config()

    def _reload_notification_templates(self):
        """重新加载通知模板"""
        from notification.notification_templates import notification_templates
        notification_templates.reload()

    def _reload_users(self):
        """重新加载用户配置"""
        from auth import load_users
        load_users()

    def _watch_loop(self):
        """监控循环"""
        logger.info("配置文件监控已启动")

        while self.running:
            try:
                changed_files = self._check_files()
                if changed_files:
                    logger.info(f"检测到配置文件变化: {changed_files}")
                    self._reload_configs(changed_files)

                time.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"配置监控循环错误: {e}")
                time.sleep(self.check_interval)

        logger.info("配置文件监控已停止")

    def start(self):
        """启动配置监控"""
        if self.running:
            logger.warning("配置监控已在运行")
            return

        self.running = True
        self.thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """停止配置监控"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)


# 全局配置监控实例
config_watcher = ConfigWatcher()


def start_config_watcher():
    """启动配置文件监控"""
    config_watcher.start()


def stop_config_watcher():
    """停止配置文件监控"""
    config_watcher.stop()


def add_config_file(file_path: str, callback: Callable = None):
    """
    添加配置文件监控

    Args:
        file_path: 文件路径
        callback: 文件变化时的回调函数

    Example:
        def on_config_change(file_path):
            print(f"配置文件已变化: {file_path}")

        add_config_file('data/custom_config.json', on_config_change)
    """
    config_watcher.add_file(file_path, callback)


if __name__ == '__main__':
    # 测试代码
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    def test_callback(file_path):
        print(f"配置文件变化回调: {file_path}")

    # 启动监控
    config_watcher.add_file('.env', test_callback)
    config_watcher.start()

    print("配置监控已启动，修改 .env 文件进行测试...")
    print("按 Ctrl+C 停止")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        config_watcher.stop()
        print("\n配置监控已停止")
