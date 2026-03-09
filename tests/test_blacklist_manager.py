#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
黑名单管理器单元测试
"""

import sys
import os
import unittest
import tempfile
import json
from unittest.mock import patch, MagicMock

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blacklist_manager import BlacklistManager


class TestBlacklistManager(unittest.TestCase):
    """黑名单管理器测试类"""

    def setUp(self):
        """测试前准备"""
        # 创建临时文件
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()

        # 创建临时黑名单管理器
        self.manager = BlacklistManager()
        self.manager.blacklist_file = self.temp_file.name
        self.manager.blacklist = {}

    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def test_add_ip(self):
        """测试添加IP"""
        result = self.manager.add_ip('192.168.1.1', expire_hours=24)
        self.assertTrue(result)
        self.assertIn('192.168.1.1', self.manager.blacklist)

    def test_add_duplicate_ip(self):
        """测试添加重复IP"""
        self.manager.add_ip('192.168.1.1')
        result = self.manager.add_ip('192.168.1.1')
        self.assertFalse(result)

    def test_remove_ip(self):
        """测试移除IP"""
        self.manager.add_ip('192.168.1.1')
        result = self.manager.remove_ip('192.168.1.1')
        self.assertTrue(result)
        self.assertNotIn('192.168.1.1', self.manager.blacklist)

    def test_remove_nonexistent_ip(self):
        """测试移除不存在的IP"""
        result = self.manager.remove_ip('192.168.1.1')
        self.assertFalse(result)

    def test_is_blocked(self):
        """测试IP是否被封锁"""
        self.manager.add_ip('192.168.1.1')
        self.assertTrue(self.manager.is_blocked('192.168.1.1'))
        self.assertFalse(self.manager.is_blocked('10.0.0.1'))

    def test_expired_ip(self):
        """测试过期IP"""
        # 添加一个1秒后过期的IP
        self.manager.add_ip('192.168.1.1', expire_hours=0.0003)  # 约1秒

        # 立即检查应该被封锁
        self.assertTrue(self.manager.is_blocked('192.168.1.1'))

        # 等待过期
        import time
        time.sleep(1.5)

        # 应该不再被封锁
        self.assertFalse(self.manager.is_blocked('192.168.1.1'))

    def test_get_stats(self):
        """测试获取统计信息"""
        self.manager.add_ip('192.168.1.1', expire_hours=24)
        self.manager.add_ip('10.0.0.1', expire_hours=0.0003)  # 很快过期
        self.manager.add_ip('172.16.0.1', expire_hours=0)  # 永不过期

        stats = self.manager.get_stats()
        self.assertEqual(stats['total'], 3)
        self.assertGreater(stats['permanent'], 0)

    def test_cleanup_expired(self):
        """测试清理过期IP"""
        self.manager.add_ip('192.168.1.1', expire_hours=0.0003)  # 很快过期

        import time
        time.sleep(1.5)

        count = self.manager.cleanup_expired()
        self.assertEqual(count, 1)
        self.assertEqual(len(self.manager.blacklist), 0)


if __name__ == '__main__':
    unittest.main()