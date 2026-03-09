#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
健康检查服务
提供HTTP接口用于监控系统检查服务状态
"""

import sys
import os
import logging
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from datetime import datetime

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from blacklist_manager import blacklist_manager
from prometheus_metrics import prometheus_metrics

logger = logging.getLogger(__name__)


class HealthCheckHandler(BaseHTTPRequestHandler):
    """健康检查处理器"""

    def do_GET(self):
        """处理GET请求"""
        if self.path == '/health' or self.path == '/':
            self.send_health_response()
        elif self.path == '/metrics':
            self.send_metrics_response()
        elif self.path == '/status':
            self.send_status_response()
        elif self.path == '/prometheus':
            self.send_prometheus_response()
        else:
            self.send_error_response(404, "Not Found")

    def send_health_response(self):
        """发送健康检查响应"""
        try:
            response = {
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'service': 'ips-syslog'
            }
            self.send_json_response(200, response)
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            self.send_error_response(500, str(e))

    def send_metrics_response(self):
        """发送指标响应"""
        try:
            stats = blacklist_manager.get_stats()
            response = {
                'timestamp': datetime.now().isoformat(),
                'blacklist': stats,
                'uptime': time.time() - HealthCheckServer.start_time
            }
            self.send_json_response(200, response)
        except Exception as e:
            logger.error(f"获取指标失败: {e}")
            self.send_error_response(500, str(e))

    def send_status_response(self):
        """发送状态响应"""
        try:
            response = {
                'timestamp': datetime.now().isoformat(),
                'service': 'ips-syslog',
                'version': '2.0.0',
                'config': {
                    'syslog_host': Config.SYSLOG_HOST,
                    'syslog_port': Config.SYSLOG_PORT,
                    'log_level': Config.LOG_LEVEL
                },
                'blacklist_stats': blacklist_manager.get_stats()
            }
            self.send_json_response(200, response)
        except Exception as e:
            logger.error(f"获取状态失败: {e}")
            self.send_error_response(500, str(e))

    def send_prometheus_response(self):
        """发送Prometheus格式指标响应"""
        try:
            metrics = prometheus_metrics.export_metrics()
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; version=0.0.4; charset=utf-8')
            self.end_headers()
            self.wfile.write(metrics.encode('utf-8'))
        except Exception as e:
            logger.error(f"导出Prometheus指标失败: {e}")
            self.send_error_response(500, str(e))

    def send_json_response(self, status_code: int, data: dict):
        """发送JSON响应"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def send_error_response(self, status_code: int, message: str):
        """发送错误响应"""
        response = {
            'status': 'error',
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        self.send_json_response(status_code, response)

    def log_message(self, format, *args):
        """覆盖日志方法，减少日志输出"""
        return


class HealthCheckServer:
    """健康检查服务器"""

    start_time = time.time()

    def __init__(self, host: str = '0.0.0.0', port: int = 8080):
        self.host = host
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        """启动健康检查服务器"""
        try:
            self.server = HTTPServer((self.host, self.port), HealthCheckHandler)
            self.thread = Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            logger.info(f"健康检查服务已启动: http://{self.host}:{self.port}")
            logger.info(f"  健康检查: http://{self.host}:{self.port}/health")
            logger.info(f"  指标数据: http://{self.host}:{self.port}/metrics")
            logger.info(f"  状态信息: http://{self.host}:{self.port}/status")
            logger.info(f"  Prometheus指标: http://{self.host}:{self.port}/prometheus")
        except Exception as e:
            logger.error(f"启动健康检查服务失败: {e}")

    def stop(self):
        """停止健康检查服务器"""
        if self.server:
            self.server.shutdown()
            logger.info("健康检查服务已停止")


# 全局健康检查服务器实例
health_check_server = None


def start_health_check(host: str = '0.0.0.0', port: int = 8080):
    """启动健康检查服务"""
    global health_check_server
    health_check_server = HealthCheckServer(host, port)
    health_check_server.start()


if __name__ == "__main__":
    # 测试代码
    import argparse

    parser = argparse.ArgumentParser(description='健康检查服务')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址')
    parser.add_argument('--port', type=int, default=8080, help='监听端口')
    args = parser.parse_args()

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 启动服务
    start_health_check(args.host, args.port)

    print(f"健康检查服务已启动: http://{args.host}:{args.port}")
    print("按 Ctrl+C 停止服务")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        if health_check_server:
            health_check_server.stop()
        print("服务已停止")