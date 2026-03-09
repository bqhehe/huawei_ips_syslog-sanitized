#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
工具函数模块单元测试
"""

import sys
import os
import time
import unittest
from unittest.mock import patch, MagicMock

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import RateLimiter, AsyncTaskRunner, async_task, retry, validate_ip


class TestRateLimiter(unittest.TestCase):
    """速率限制器测试类"""

    def setUp(self):
        """测试前准备"""
        self.limiter = RateLimiter(max_requests=3, time_window=2)

    def test_rate_limiter_within_limit(self):
        """测试在限制内的请求"""
        for i in range(3):
            self.assertTrue(self.limiter.is_allowed('test_ip'))

    def test_rate_limiter_exceeds_limit(self):
        """测试超过限制的请求"""
        for i in range(3):
            self.limiter.is_allowed('test_ip')

        # 第4个请求应该被拒绝
        self.assertFalse(self.limiter.is_allowed('test_ip'))

    def test_rate_limiter_reset_after_window(self):
        """测试时间窗口后重置"""
        for i in range(3):
            self.limiter.is_allowed('test_ip')

        # 等待时间窗口过期
        time.sleep(2.5)

        # 应该再次允许请求
        self.assertTrue(self.limiter.is_allowed('test_ip'))

    def test_rate_limiter_different_keys(self):
        """测试不同键的独立限制"""
        for i in range(3):
            self.limiter.is_allowed('ip1')

        # 不同键应该不受影响
        self.assertTrue(self.limiter.is_allowed('ip2'))


class TestAsyncTaskRunner(unittest.TestCase):
    """异步任务运行器测试类"""

    def setUp(self):
        """测试前准备"""
        self.runner = AsyncTaskRunner(max_workers=2)

    def test_async_task_execution(self):
        """测试异步任务执行"""
        result = []

        def task(value):
            result.append(value)

        self.runner.submit(task, 1)
        self.runner.submit(task, 2)

        # 等待任务完成
        time.sleep(0.5)

        self.assertIn(1, result)
        self.assertIn(2, result)

    def test_async_task_worker_limit(self):
        """测试工作线程限制"""
        executed = []

        def long_task():
            time.sleep(1)
            executed.append(1)

        # 提交超过限制的任务
        for i in range(5):
            self.runner.submit(long_task)

        time.sleep(0.2)
        # 应该只有2个任务在执行
        self.assertLessEqual(len(executed), 2)


class TestRetryDecorator(unittest.TestCase):
    """重试装饰器测试类"""

    def test_retry_success(self):
        """测试重试成功"""
        call_count = [0]

        @retry(max_attempts=3, delay=0.1)
        def failing_function():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("失败")
            return "成功"

        result = failing_function()
        self.assertEqual(result, "成功")
        self.assertEqual(call_count[0], 3)

    def test_retry_failure(self):
        """测试重试失败"""
        @retry(max_attempts=2, delay=0.1)
        def always_failing_function():
            raise Exception("总是失败")

        with self.assertRaises(Exception):
            always_failing_function()


class TestValidateIp(unittest.TestCase):
    """IP验证测试类"""

    def test_validate_ip_valid(self):
        """测试有效IP"""
        self.assertTrue(validate_ip('192.168.1.1'))
        self.assertTrue(validate_ip('10.0.0.1'))
        self.assertTrue(validate_ip('172.16.0.1'))

    def test_validate_ip_invalid(self):
        """测试无效IP"""
        self.assertFalse(validate_ip('256.256.256.256'))
        self.assertFalse(validate_ip('invalid'))
        self.assertFalse(validate_ip(''))


if __name__ == '__main__':
    unittest.main()