#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置模块单元测试
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config, validate_ip, validate_config


class TestConfig(unittest.TestCase):
    """配置测试类"""

    def test_validate_ip_valid(self):
        """测试有效IP地址"""
        self.assertTrue(validate_ip('192.168.1.1'))
        self.assertTrue(validate_ip('10.0.0.1'))
        self.assertTrue(validate_ip('172.16.0.1'))

    def test_validate_ip_invalid(self):
        """测试无效IP地址"""
        self.assertFalse(validate_ip('256.256.256.256'))
        self.assertFalse(validate_ip('invalid'))
        self.assertFalse(validate_ip(''))

    @patch('config.os.getenv')
    def test_config_defaults(self, mock_getenv):
        """测试默认配置"""
        mock_getenv.return_value = None
        self.assertEqual(Config.FW_IP, '192.168.1.1')
        self.assertEqual(Config.SYSLOG_PORT, 514)


if __name__ == '__main__':
    unittest.main()