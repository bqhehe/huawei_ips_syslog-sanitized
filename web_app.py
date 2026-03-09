#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Web管理界面
提供可视化的Web管理界面，集成Prometheus监控和Grafana可视化
"""

import sys
import os
import json
import logging
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import urllib.parse
import time
import http.cookies

# 添加父目录到路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from config import Config, update_env_file
from blacklist_manager import blacklist_manager
from whitelist_manager import whitelist_manager
from audit_logger import audit_logger
from prometheus_metrics import prometheus_metrics
from rule_engine import rule_engine
from auth import verify_user, create_session, verify_session, destroy_session, change_password
from utils import global_log_buffer
from notification.notification_config import notification_config
from notification.notification_sender import notification_sender
from defense.ips_ssh import ips_ssh, undo_blacklist
from ip_geo_locator import ip_geo_locator

# 数据库模块
try:
    from database.dao import alert_dao
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("数据库模块不可用，告警将仅从文件读取")

# 分析引擎模块
try:
    from analysis_engine import analysis_engine
    ANALYSIS_AVAILABLE = True
except ImportError:
    ANALYSIS_AVAILABLE = False
    logger.warning("分析引擎模块不可用")

logger = logging.getLogger(__name__)


class WebHandler(BaseHTTPRequestHandler):
    """Web请求处理器"""

    def do_GET(self):
        """处理GET请求"""
        parsed_path = urllib.parse.urlparse(self.path)
        
        # 公开页面：登录页面
        if parsed_path.path in ['/', '/index.html', '/login.html']:
            self.send_html_response(self.get_login_html())
            return

        if parsed_path.path.startswith('/static/'):
            self.serve_static_file(parsed_path.path)
            return

        # API登录接口
        elif parsed_path.path == '/api/login':
            self.send_error_response(405, "Method Not Allowed")
            return

        # 其他页面需要认证
        session_id = self.get_session_id()
        if not session_id or not verify_session(session_id):
            if parsed_path.path.startswith('/api/'):
                self.send_response(401)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Unauthorized', 'message': '未登录或会话已过期'}).encode('utf-8'))
            else:
                self.send_html_response(self.get_login_html())
            return
        
        if parsed_path.path == '/dashboard.html':
            self.send_html_response(self.get_dashboard_html())
        elif parsed_path.path == '/api/blacklist':
            self.send_json_response(blacklist_manager.get_all_ips())
        elif parsed_path.path == '/api/blacklist/stats':
            self.send_json_response(blacklist_manager.get_stats())
        elif parsed_path.path == '/api/blacklist/export':
            # 导出黑名单（GET方式）
            ips = blacklist_manager.get_all_ips()
            query_params = urllib.parse.parse_qs(parsed_path.query)
            export_format = query_params.get('format', ['text'])[0]  # text, csv, json

            if export_format == 'json':
                self.send_json_response({'ips': ips})
            elif export_format == 'csv':
                csv_content = '# IP, Added At, Expire At, Status\n'
                for ip_info in ips:
                    csv_content += f"{ip_info['ip']}, {ip_info['added_at']}, {ip_info.get('expire_at', 'N/A')}, {ip_info['status']}\n"
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv; charset=utf-8')
                self.send_header('Content-Disposition', 'attachment; filename="blacklist.csv"')
                self.end_headers()
                self.wfile.write(csv_content.encode('utf-8'))
            else:  # text format (default)
                text_content = '# IPS Blacklist Export\n'
                text_content += f'# Generated: {datetime.now().isoformat()}\n\n'
                for ip_info in ips:
                    text_content += f"{ip_info['ip']}\n"
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Disposition', 'attachment; filename="blacklist.txt"')
                self.end_headers()
                self.wfile.write(text_content.encode('utf-8'))
        elif parsed_path.path == '/api/whitelist':
            self.send_json_response(whitelist_manager.get_all_ips())
        elif parsed_path.path == '/api/whitelist/stats':
            self.send_json_response(whitelist_manager.get_stats())
        elif parsed_path.path == '/api/audit':
            count = int(urllib.parse.parse_qs(parsed_path.query).get('count', [100])[0])
            self.send_json_response(audit_logger.get_recent_logs(count))
        elif parsed_path.path == '/api/metrics':
            self.send_json_response(prometheus_metrics.export_metrics())
        elif parsed_path.path == '/api/rules':
            self.send_json_response(rule_engine.list_rules())
        elif parsed_path.path == '/api/status':
            # 获取数据库告警统计
            alert_stats = self._get_alert_stats_from_db()
            self.send_json_response({
                'timestamp': datetime.now().isoformat(),
                'service': 'ips-syslog',
                'version': '2.0.0',
                'uptime': int(time.time() - prometheus_metrics.start_time),
                'blacklist_stats': blacklist_manager.get_stats(),
                'alert_stats': alert_stats,
                'prometheus_metrics': {
                    'alerts_by_severity': prometheus_metrics.alerts_by_severity,
                    'alerts_by_attack_type': prometheus_metrics.alerts_by_attack_type
                }
            })
        elif parsed_path.path == '/api/prometheus/raw':
            self.send_prometheus_response()
        elif parsed_path.path == '/api/logout':
            if session_id:
                destroy_session(session_id)
            self.send_json_response({'success': True})
        elif parsed_path.path == '/api/alerts':
            count = int(urllib.parse.parse_qs(parsed_path.query).get('count', [50])[0])
            # 直接从数据库读取（告警已实时写入，不需要从文件同步）
            if DB_AVAILABLE:
                try:
                    self.send_json_response(alert_dao.get_recent(count))
                except Exception as e:
                    logger.error(f"从数据库获取告警失败: {e}")
                    self.send_json_response(self.get_recent_alerts(count))
            else:
                self.send_json_response(self.get_recent_alerts(count))
        elif parsed_path.path == '/api/logs':
            # 获取最近接收的日志（包括SESSION日志）
            count = int(urllib.parse.parse_qs(parsed_path.query).get('count', [100])[0])
            log_type = urllib.parse.parse_qs(parsed_path.query).get('type', [None])[0]
            self.send_json_response(global_log_buffer.get_recent(count, log_type))
        elif parsed_path.path == '/api/logs/stats':
            # 获取日志统计信息
            self.send_json_response(global_log_buffer.get_stats())
        elif parsed_path.path == '/api/notification/config':
            # 获取通知配置
            self.send_json_response(notification_config.get_config())
        elif parsed_path.path == '/api/firewall/status':
            # 获取防火墙连接状态
            from defense.ips_ssh import FirewallSSH
            firewall = FirewallSSH()
            try:
                connected = firewall.connect(timeout=5)
                if connected:
                    firewall.close()
                    self.send_json_response({'connected': True, 'message': '防火墙连接正常'})
                else:
                    self.send_json_response({'connected': False, 'message': '防火墙连接失败'})
            except Exception as e:
                logger.error(f"检查防火墙状态失败: {e}")
                self.send_json_response({'connected': False, 'message': f'连接错误: {str(e)}'})
        elif parsed_path.path == '/api/config/reload':
            # 手动重新加载配置
            try:
                from config_watcher import config_watcher
                config_watcher._reload_configs(list(config_watcher.watched_files.keys()))
                self.send_json_response({'success': True, 'message': '配置已重新加载'})
            except Exception as e:
                logger.error(f"重新加载配置失败: {e}")
                self.send_json_response({'success': False, 'message': f'重新加载失败: {str(e)}'})

        # 分析相关API端点
        elif parsed_path.path.startswith('/api/analysis/'):
            if not ANALYSIS_AVAILABLE:
                self.send_json_response({'error': '分析引擎模块不可用'})
                return

            query_params = urllib.parse.parse_qs(parsed_path.query)
            hours = int(query_params.get('hours', [24])[0])

            if parsed_path.path == '/api/analysis/overview':
                self.send_json_response(analysis_engine.get_overview_stats(hours))
            elif parsed_path.path == '/api/analysis/trend':
                interval = int(query_params.get('interval', [1])[0])
                self.send_json_response(analysis_engine.get_trend_analysis(hours, interval))
            elif parsed_path.path == '/api/analysis/attack-types':
                self.send_json_response(analysis_engine.get_attack_type_distribution(hours))
            elif parsed_path.path == '/api/analysis/top-attackers':
                limit = int(query_params.get('limit', [20])[0])
                self.send_json_response(analysis_engine.get_top_attackers(hours, limit))
            elif parsed_path.path == '/api/analysis/top-targets':
                limit = int(query_params.get('limit', [20])[0])
                self.send_json_response(analysis_engine.get_top_targets(hours, limit))
            elif parsed_path.path == '/api/analysis/time-distribution':
                self.send_json_response(analysis_engine.get_time_distribution(hours))
            elif parsed_path.path == '/api/analysis/geo-distribution':
                self.send_json_response(analysis_engine.get_geo_distribution(hours))
            elif parsed_path.path == '/api/analysis/correlation':
                self.send_json_response(analysis_engine.get_correlation_analysis(hours))
            elif parsed_path.path == '/api/analysis/report':
                self.send_json_response(analysis_engine.generate_analysis_report(hours))
            else:
                self.send_error_response(404, "Analysis endpoint not found")
        else:
            self.send_error_response(404, "Not Found")

    def do_POST(self):
        """处理POST请求"""
        parsed_path = urllib.parse.urlparse(self.path)
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')

        # 登录接口（不需要认证）
        if parsed_path.path == '/api/login':
            data = json.loads(post_data)
            username = data.get('username')
            password = data.get('password')
            
            if verify_user(username, password):
                session_id = create_session(username)
                self.send_json_response({'success': True, 'session_id': session_id})
            else:
                self.send_json_response({'success': False, 'message': '用户名或密码错误'})
            return
        
        # 其他接口需要认证
        session_id = self.get_session_id()
        if not session_id or not verify_session(session_id):
            self.send_response(401)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'message': '未登录或会话已过期'}).encode('utf-8'))
            return

        if parsed_path.path == '/api/blacklist/add':
            data = json.loads(post_data)
            ip = data.get('ip')
            expire_hours = data.get('expire_hours', 24)

            # 先添加到本地黑名单
            result = blacklist_manager.add_ip(ip, expire_hours)

            # 如果本地添加成功，同步到防火墙
            firewall_success = False
            if result:
                try:
                    firewall_success = ips_ssh(ip, expire_hours)
                    if firewall_success:
                        logger.info(f"手动添加: IP {ip} 已同步到防火墙黑名单")
                    else:
                        logger.warning(f"手动添加: IP {ip} 本地添加成功但防火墙同步失败")
                except Exception as e:
                    logger.error(f"同步到防火墙失败: {e}")

            # 返回结果：本地成功即返回成功，防火墙状态作为附加信息
            self.send_json_response({
                'success': result,
                'firewall_synced': firewall_success
            })

        elif parsed_path.path == '/api/blacklist/remove':
            data = json.loads(post_data)
            ip = data.get('ip')

            # 从本地移除
            result = blacklist_manager.remove_ip(ip)

            # 同步到防火墙
            firewall_success = False
            if result:
                try:
                    firewall_success = undo_blacklist(ip)
                    if firewall_success:
                        logger.info(f"手动移除: IP {ip} 已从防火墙黑名单移除")
                    else:
                        logger.warning(f"手动移除: IP {ip} 本地移除成功但防火墙同步失败")
                except Exception as e:
                    logger.error(f"同步防火墙移除失败: {e}")

            self.send_json_response({
                'success': result,
                'firewall_synced': firewall_success
            })

        elif parsed_path.path == '/api/blacklist/cleanup':
            count = blacklist_manager.cleanup_expired()
            self.send_json_response({'success': True, 'count': count})

        elif parsed_path.path == '/api/blacklist/bulk-add':
            # 批量添加IP
            data = json.loads(post_data)
            ips = data.get('ips', [])
            expire_hours = data.get('expire_hours', 24)

            results = {'success': 0, 'failed': 0, 'firewall_synced': 0, 'errors': []}
            for ip in ips:
                if blacklist_manager.add_ip(ip.strip(), expire_hours):
                    results['success'] += 1
                    # 尝试同步到防火墙
                    try:
                        if ips_ssh(ip.strip(), expire_hours):
                            results['firewall_synced'] += 1
                    except Exception as e:
                        logger.error(f"批量添加: IP {ip.strip()} 同步防火墙失败: {e}")
                else:
                    results['failed'] += 1
                    results['errors'].append({'ip': ip, 'reason': '添加失败'})

            self.send_json_response(results)

        elif parsed_path.path == '/api/blacklist/bulk-remove':
            # 批量移除IP
            data = json.loads(post_data)
            ips = data.get('ips', [])

            results = {'success': 0, 'failed': 0, 'firewall_synced': 0, 'errors': []}
            for ip in ips:
                if blacklist_manager.remove_ip(ip.strip()):
                    results['success'] += 1
                    # 尝试同步到防火墙
                    try:
                        if undo_blacklist(ip.strip()):
                            results['firewall_synced'] += 1
                    except Exception as e:
                        logger.error(f"批量移除: IP {ip.strip()} 同步防火墙失败: {e}")
                else:
                    results['failed'] += 1
                    results['errors'].append({'ip': ip, 'reason': '移除失败'})

            self.send_json_response(results)

        elif parsed_path.path == '/api/blacklist/import':
            # 导入黑名单（支持文本或CSV格式）
            data = json.loads(post_data)
            content = data.get('content', '')
            expire_hours = data.get('expire_hours', 24)

            # 解析IP列表
            ips = []
            for line in content.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    # 支持逗号分隔或纯IP
                    for ip in line.replace(',', ' ').split():
                        ip = ip.strip()
                        if ip:
                            ips.append(ip)

            results = {'success': 0, 'failed': 0, 'errors': [], 'total': len(ips)}
            for ip in ips:
                if blacklist_manager.add_ip(ip, expire_hours):
                    results['success'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({'ip': ip, 'reason': '添加失败'})

            self.send_json_response(results)

        elif parsed_path.path == '/api/blacklist/export':
            # 导出黑名单
            ips = blacklist_manager.get_all_ips()
            export_format = json.loads(post_data).get('format', 'text')  # text, csv, json

            if export_format == 'json':
                self.send_json_response({'ips': ips})
            elif export_format == 'csv':
                csv_content = '# IP, Added At, Expire At, Status\n'
                for ip_info in ips:
                    csv_content += f"{ip_info['ip']}, {ip_info['added_at']}, {ip_info.get('expire_at', 'N/A')}, {ip_info['status']}\n"
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv; charset=utf-8')
                self.send_header('Content-Disposition', 'attachment; filename="blacklist.csv"')
                self.end_headers()
                self.wfile.write(csv_content.encode('utf-8'))
            else:  # text format (default)
                text_content = '# IPS Blacklist Export\n'
                text_content += f'# Generated: {datetime.now().isoformat()}\n\n'
                for ip_info in ips:
                    text_content += f"{ip_info['ip']}\n"
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.send_header('Content-Disposition', 'attachment; filename="blacklist.txt"')
                self.end_headers()
                self.wfile.write(text_content.encode('utf-8'))
            return

        elif parsed_path.path == '/api/whitelist/add':
            # 添加到白名单
            data = json.loads(post_data)
            ip_or_cidr = data.get('ip')
            description = data.get('description', '')

            if not ip_or_cidr:
                self.send_json_response({'success': False, 'message': 'IP地址或网段不能为空'})
                return

            result = whitelist_manager.add_ip(ip_or_cidr, description)
            self.send_json_response(result)

        elif parsed_path.path == '/api/whitelist/remove':
            # 从白名单移除
            data = json.loads(post_data)
            ip_or_cidr = data.get('ip')

            if not ip_or_cidr:
                self.send_json_response({'success': False, 'message': 'IP地址或网段不能为空'})
                return

            result = whitelist_manager.remove_ip(ip_or_cidr)
            self.send_json_response(result)

        elif parsed_path.path == '/api/whitelist/import':
            # 导入白名单（从配置文件）
            result = whitelist_manager.import_from_config()
            self.send_json_response(result)

        elif parsed_path.path == '/api/logout':
            destroy_session(session_id)
            self.send_json_response({'success': True, 'message': '已退出登录'})

        elif parsed_path.path == '/api/change-password':
            data = json.loads(post_data)
            session_id = self.get_session_id()
            if not session_id:
                self.send_json_response({'success': False, 'message': '未登录或会话已过期'})
                return

            session = verify_session(session_id)
            if not session:
                self.send_json_response({'success': False, 'message': '未登录或会话已过期'})
                return

            username = session['username']
            old_password = data.get('old_password')
            new_password = data.get('new_password')

            if not old_password or not new_password:
                self.send_json_response({'success': False, 'message': '旧密码和新密码不能为空'})
                return

            if change_password(username, old_password, new_password):
                self.send_json_response({'success': True, 'message': '密码修改成功'})
            else:
                self.send_json_response({'success': False, 'message': '旧密码错误'})

        elif parsed_path.path == '/api/config/firewall':
            data = json.loads(post_data)
            session_id = self.get_session_id()
            if not session_id:
                self.send_json_response({'success': False, 'message': '未登录或会话已过期'})
                return

            session = verify_session(session_id)
            if not session:
                self.send_json_response({'success': False, 'message': '未登录或会话已过期'})
                return

            fw_ip = data.get('fw_ip')
            fw_username = data.get('fw_username')
            fw_password = data.get('fw_password')

            updates = {}
            if fw_ip:
                updates['FW_IP'] = fw_ip
            if fw_username:
                updates['FW_USERNAME'] = fw_username
            if fw_password:
                updates['FW_PASSWORD'] = fw_password

            if updates:
                try:
                    update_env_file(updates)
                    self.send_json_response({'success': True, 'message': '防火墙配置已更新'})
                except Exception as e:
                    logger.error(f"更新配置失败: {e}")
                    self.send_json_response({'success': False, 'message': f'更新配置失败: {str(e)}'})
            else:
                self.send_json_response({'success': False, 'message': '没有检测到需要更新的配置'})

        elif parsed_path.path == '/api/notification/update':
            # 更新通知配置
            data = json.loads(post_data)
            channel = data.get('channel')
            enabled = data.get('enabled', False)

            if not channel:
                self.send_json_response({'success': False, 'message': '缺少channel参数'})
                return

            # 提取配置参数
            config_params = {}
            if channel == 'wechat':
                config_params['webhook_url'] = data.get('webhook_url')
            elif channel == 'dingtalk':
                config_params['webhook_url'] = data.get('webhook_url')
                config_params['sign_secret'] = data.get('sign_secret')
            elif channel == 'feishu':
                config_params['webhook_url'] = data.get('webhook_url')
                config_params['sign_secret'] = data.get('sign_secret')
            elif channel == 'email':
                config_params['smtp_host'] = data.get('smtp_host')
                config_params['smtp_user'] = data.get('smtp_user')
                config_params['smtp_password'] = data.get('smtp_password')
                config_params['sender'] = data.get('sender')
                config_params['recipients'] = data.get('recipients', [])

            if notification_config.update_channel(channel, enabled, **config_params):
                # 重新加载通知发送器的配置
                notification_sender.reload_config()
                self.send_json_response({'success': True, 'message': f'{channel} 通知配置已更新'})
            else:
                self.send_json_response({'success': False, 'message': '更新通知配置失败'})

        elif parsed_path.path == '/api/notification/test':
            # 测试通知
            data = json.loads(post_data)
            channel = data.get('channel')

            if not channel:
                self.send_json_response({'success': False, 'message': '缺少channel参数'})
                return

            # 使用新的notification_sender进行测试
            test_message = """【测试消息】IPS Syslog 威胁防护告警
攻击源IP: 8.8.8.8
目的地址: 192.168.1.1
攻击时间: 2026-02-28 12:00:00
攻击类型: Directory Traversal
严重性: medium

这是一条测试消息，用于验证通知配置是否正确。"""

            try:
                # 重新加载配置以确保使用最新设置
                notification_sender.reload_config()

                if channel == 'wechat':
                    result = notification_sender._send_wechat(test_message)
                elif channel == 'dingtalk':
                    result = notification_sender._send_dingtalk(test_message)
                elif channel == 'feishu':
                    result = notification_sender._send_feishu(test_message)
                elif channel == 'email':
                    result = notification_sender._send_email(test_message)
                else:
                    self.send_json_response({'success': False, 'message': f'不支持的通知渠道: {channel}'})
                    return

                if result:
                    self.send_json_response({'success': True, 'message': f'{channel} 测试通知发送成功'})
                else:
                    self.send_json_response({'success': False, 'message': f'{channel} 测试通知发送失败，请检查配置'})
            except Exception as e:
                logger.error(f"测试通知失败: {e}")
                self.send_json_response({'success': False, 'message': f'测试失败: {str(e)}'})

        elif parsed_path.path == '/api/analysis/export':
            # 导出分析报告
            if not ANALYSIS_AVAILABLE:
                self.send_json_response({'error': '分析引擎模块不可用'})
                return

            data = json.loads(post_data)
            hours = data.get('hours', 24)
            format_type = data.get('format', 'json')  # json, csv, html

            try:
                report = analysis_engine.generate_analysis_report(hours)

                if format_type == 'json':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Content-Disposition', f'attachment; filename="analysis_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"')
                    self.end_headers()
                    self.wfile.write(json.dumps(report, ensure_ascii=False, indent=2).encode('utf-8'))

                elif format_type == 'html':
                    html_report = self._generate_html_report(report)
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.send_header('Content-Disposition', f'attachment; filename="analysis_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html"')
                    self.end_headers()
                    self.wfile.write(html_report.encode('utf-8'))

                else:
                    self.send_json_response({'error': f'不支持的导出格式: {format_type}'})

            except Exception as e:
                logger.error(f"导出分析报告失败: {e}")
                self.send_json_response({'error': f'导出失败: {str(e)}'})

        else:
            self.send_error_response(404, "Not Found")

    def get_session_id(self):
        """获取会话ID"""
        cookie_header = self.headers.get('Cookie')
        if not cookie_header:
            return None

        # 尝试使用 SimpleCookie 解析
        try:
            cookies = http.cookies.SimpleCookie(cookie_header)
            if 'session_id' in cookies:
                return cookies['session_id'].value
        except Exception:
            pass

        # 回退到简单的字符串解析
        for pair in cookie_header.split(';'):
            pair = pair.strip()
            if pair.startswith('session_id='):
                return pair.split('=', 1)[1].strip()

        return None

    def send_html_response(self, html_content):
        """发送HTML响应"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Security-Policy', "default-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://gw.alipayobjects.com; img-src 'self' data: https:; font-src 'self' data: https://gw.alipayobjects.com; connect-src 'self' https://cdn.jsdelivr.net https://unpkg.com https://geo.datav.aliyun.com;")
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))

    def send_json_response(self, data):
        """发送JSON响应"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))

    def send_prometheus_response(self):
        """发送Prometheus格式指标响应"""
        metrics = prometheus_metrics.export_metrics()
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; version=0.0.4; charset=utf-8')
        self.end_headers()
        self.wfile.write(metrics.encode('utf-8'))

    def send_error_response(self, status_code, message):
        """发送错误响应"""
        response = {
            'status': 'error',
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

    def serve_static_file(self, path):
        import os
        import mimetypes

        file_path = os.path.join(BASE_DIR, path.lstrip('/'))

        if not os.path.exists(file_path):
            self.send_error_response(404, "Not Found")
            return

        with open(file_path, 'rb') as f:
            content = f.read()

        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = 'application/octet-stream'

        self.send_response(200)
        self.send_header('Content-Type', f'{mime_type}; charset=utf-8')
        self.send_header('Cache-Control', 'max-age=3600')
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        """覆盖日志方法，减少日志输出"""
        return

    def get_login_html(self):
        """生成登录页面HTML"""
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://gw.alipayobjects.com; img-src 'self' data: https:; font-src 'self' data: https://gw.alipayobjects.com; connect-src 'self' http://localhost:8081;">
    <title>登录 - IPS Syslog 自动响应系统</title>
    <link rel="stylesheet" href="/static/login.css?v=202601221018">
</head>
<body>
    <div class="login-container">
        <h1>IPS Syslog</h1>
        <p>自动响应系统</p>
        
        <div class="error-message" id="error-message"></div>
        
        <form id="login-form">
            <div class="form-group">
                <label for="username">用户名</label>
                <input type="text" id="username" name="username" required autofocus>
            </div>
            
            <div class="form-group">
                <label for="password">密码</label>
                <input type="password" id="password" name="password" required>
            </div>
            
            <button type="submit" class="btn btn-primary" id="login-btn">登录</button>
        </form>
        
        <div class="info-box">
            <strong>默认账号:</strong> admin / admin123<br>
            首次登录后请及时修改密码
        </div>
    </div>

    <script>
        const loginForm = document.getElementById('login-form');
        const loginBtn = document.getElementById('login-btn');
        const errorMessage = document.getElementById('error-message');

        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            
            loginBtn.disabled = true;
            loginBtn.textContent = '登录中...';
            errorMessage.classList.remove('show');
            
            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // 保存会话ID
                    document.cookie = `session_id=${result.session_id}; path=/; max-age=3600; SameSite=Lax`;
                    // 跳转到仪表板
                    console.log('登录成功，跳转到仪表板');
                    window.location.href = '/dashboard.html';
                } else {
                    errorMessage.textContent = result.message || '登录失败';
                    errorMessage.classList.add('show');
                    loginBtn.disabled = false;
                    loginBtn.textContent = '登录';
                }
            } catch (error) {
                console.error('登录错误:', error);
                errorMessage.textContent = '网络错误，请重试';
                errorMessage.classList.add('show');
                loginBtn.disabled = false;
                loginBtn.textContent = '登录';
            }
        });

        // 检查是否已登录
        async function checkAlreadyLoggedIn() {
            const cookies = document.cookie.split(';');
            for (let cookie of cookies) {
                const [name, value] = cookie.trim().split('=');
                if (name === 'session_id' && value) {
                    try {
                        const response = await fetch('/api/status');
                        if (response.ok) {
                            // session 有效，跳转到仪表板
                            window.location.href = '/dashboard.html';
                        } else {
                            // session 无效，清除cookie
                            document.cookie = 'session_id=; path=/; max-age=0';
                        }
                    } catch (error) {
                        console.error('检查登录状态失败:', error);
                    }
                    break;
                }
            }
        }

        // 页面加载时检查是否已登录
        checkAlreadyLoggedIn();
    </script>
</body>
</html>'''

    def get_dashboard_html(self):
        """生成仪表板HTML"""
        with open('dashboard.html', 'r', encoding='utf-8') as f:
            return f.read()

    def get_recent_alerts(self, count: int = 50):
        """获取最近的告警记录"""
        import re
        from collections import defaultdict

        alerts = []

        try:
            # 读取攻击记录文件
            att_file_path = os.path.join(BASE_DIR, 'data', 'Att.txt')
            if not os.path.exists(att_file_path):
                return []

            with open(att_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 逐行解析
            for line in lines:
                line = line.strip()
                if not line or '%%01IPS/4/' not in line:
                    continue

                try:
                    # 提取时间戳和设备名
                    timestamp = '-'
                    device = 'Firewall'

                    # 提取 PRI 和 时间部分
                    pri_match = re.match(r'<(\d+)>(.+)', line)
                    if pri_match:
                        rest = pri_match.group(2)
                    else:
                        rest = line

                    # 解析时间戳
                    time_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', rest)
                    if time_match:
                        timestamp = time_match.group(1)
                    else:
                        # 尝试其他时间格式
                        time_match = re.search(r'(\w{3}\s+\d+\s+\d{4}\s+\d{2}:\d{2}:\d{2})', rest)
                        if time_match:
                            timestamp = time_match.group(1)

                    # 解析设备名（通常是第一个非时间字符串）
                    device_match = re.search(r'([A-Za-z0-9_#\-]+)\s+%%01IPS/4/', rest)
                    if device_match:
                        device = device_match.group(1)

                    # 提取括号内的内容 - 使用最后一个括号对
                    bracket_content = ''
                    last_open = line.rfind('(')
                    last_close = line.rfind(')')
                    if last_open < last_close:
                        bracket_content = line[last_open+1:last_close]

                    # 解析键值对 - 在括号内容中查找
                    src_ip = re.search(r'SrcIp\s*=\s*"?([\d.]+)"?', bracket_content or line)
                    dst_ip = re.search(r'DstIp\s*=\s*"?([\d.]+)"?', bracket_content or line)
                    src_port = re.search(r'SrcPort\s*=\s*"?(\d+)"?', bracket_content or line)
                    dst_port = re.search(r'DstPort\s*=\s*"?(\d+)"?', bracket_content or line)
                    protocol = re.search(r'Protocol\s*=\s*"?(\w+)"?', bracket_content or line)
                    severity = re.search(r'Severity\s*=\s*"?(\w+)"?', bracket_content or line)
                    action = re.search(r'Action\s*=\s*"?(\w+)"?', bracket_content or line)

                    # 解析攻击类型/签名名称
                    attack_type = 'Unknown'
                    sign_name = re.search(r'SignName\s*=\s*"([^"]+)"', bracket_content or rest)
                    if sign_name:
                        attack_type = sign_name.group(1)
                    else:
                        # 尝试 Attack 字段
                        attack_match = re.search(r'Attack\s*=\s*"([^"]+)"', bracket_content or rest)
                        if attack_match:
                            attack_type = attack_match.group(1)
                        else:
                            # 尝试 Event 字段
                            event_match = re.search(r'Event\s*=\s*"([^"]+)"', bracket_content or rest)
                            if event_match:
                                attack_type = event_match.group(1)

                    # 获取严重性
                    sev_value = severity.group(1).lower() if severity else 'medium'

                    # 获取源IP
                    src_ip_value = src_ip.group(1) if src_ip else 'N/A'

                    # 查询IP地理位置信息
                    geo_info = {}
                    if src_ip_value and src_ip_value != 'N/A':
                        try:
                            geo_info = ip_geo_locator.lookup(src_ip_value)
                        except Exception as e:
                            logger.debug(f"查询IP地理位置失败 ({src_ip_value}): {e}")

                    # 构建告警对象
                    alert = {
                        'timestamp': timestamp,
                        'device': device,
                        'src_ip': src_ip_value,
                        'dst_ip': dst_ip.group(1) if dst_ip else 'N/A',
                        'src_port': src_port.group(1) if src_port else 'N/A',
                        'dst_port': dst_port.group(1) if dst_port else 'N/A',
                        'protocol': protocol.group(1) if protocol else 'N/A',
                        'event': attack_type,
                        'attack_type': attack_type,
                        'detect_time': timestamp,
                        'severity': sev_value,
                        'action': action.group(1) if action else 'block',
                        'raw_log': line[:500],
                        # 地理位置信息
                        'geo_country_code': geo_info.get('country_code'),
                        'geo_country_name': geo_info.get('country_name'),
                        'geo_country_flag': geo_info.get('country_flag'),
                        'geo_city': geo_info.get('city'),
                        'geo_latitude': geo_info.get('latitude'),
                        'geo_longitude': geo_info.get('longitude'),
                        'geo_timezone': geo_info.get('timezone'),
                        'geo_display': f"{geo_info.get('country_flag', '🌍')} {geo_info.get('country_name', '未知')}" +
                                      (f"-{geo_info.get('city')}" if geo_info.get('city') else '')
                    }
                    alerts.append(alert)

                except Exception as e:
                    # 跳过解析失败的行
                    continue

            # 返回最新的N条记录（倒序）
            alerts = list(reversed(alerts))[:count]

        except Exception as e:
            logger.error(f"读取告警记录失败: {e}")

        return alerts

    def _sync_alerts_to_db(self):
        """同步告警记录到数据库"""
        if not DB_AVAILABLE:
            return

        try:
            # 读取文件中的告警
            alerts = self.get_recent_alerts(500)  # 获取更多记录进行同步

            # 写入数据库（使用 INSERT OR IGNORE 避免重复）
            for alert in alerts:
                try:
                    alert_dao.add(
                        src_ip=alert.get('src_ip', 'N/A'),
                        dst_ip=alert.get('dst_ip', 'N/A'),
                        src_port=int(alert.get('src_port', 0)) if alert.get('src_port', 'N/A') != 'N/A' else None,
                        dst_port=int(alert.get('dst_port', 0)) if alert.get('dst_port', 'N/A') != 'N/A' else None,
                        protocol=alert.get('protocol', 'N/A'),
                        attack_type=alert.get('event', 'Unknown'),
                        severity=alert.get('severity', 'medium'),
                        action='block',  # 默认动作
                        raw_log=alert.get('raw_log', ''),
                        device=alert.get('device', 'Firewall'),
                        detect_time=alert.get('detect_time', alert.get('timestamp'))
                    )
                except Exception as e:
                    # 忽略重复记录等错误
                    pass

        except Exception as e:
            logger.error(f"同步告警到数据库失败: {e}")

    def _get_alert_stats_from_db(self) -> dict:
        """从数据库获取告警统计数据"""
        if not DB_AVAILABLE:
            return {
                'total': 0,
                'today': 0,
                'week': 0,
                'month': 0,
                'critical': 0
            }

        try:
            from database.dao import alert_dao
            return alert_dao.get_alert_stats()
        except Exception as e:
            logger.error(f"获取告警统计失败: {e}")
            return {
                'total': 0,
                'today': 0,
                'week': 0,
                'month': 0,
                'critical': 0
            }

    def _get_severity_from_event(self, event: str) -> str:
        """根据事件类型判断严重性"""
        event_lower = event.lower()

        # 严重级别
        critical_keywords = ['mining', 'malware', 'trojan', 'botnet', 'ransomware', 'exploit']
        if any(kw in event_lower for kw in critical_keywords):
            return 'critical'

        # 高级别
        high_keywords = ['brute force', 'injection', 'sql', 'xss', 'cve', 'backdoor']
        if any(kw in event_lower for kw in high_keywords):
            return 'high'

        # 中级别
        medium_keywords = ['scan', 'probe', 'ddos', 'dns', 'flood']
        if any(kw in event_lower for kw in medium_keywords):
            return 'medium'

        # 低级别
        return 'low'

    def _generate_html_report(self, report: dict) -> str:
        """生成HTML格式的分析报告"""
        overview = report.get('overview', {})
        attack_types = report.get('attack_types', {})
        top_attackers = report.get('top_attackers', [])
        top_targets = report.get('top_targets', [])

        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPS安全分析报告 - {report.get("time_range", "N/A")}</title>
    <style>
        body {{ font-family: "Microsoft YaHei", Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; border-left: 4px solid #2196F3; padding-left: 10px; }}
        .meta {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .stat-card {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; }}
        .stat-card.critical {{ background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }}
        .stat-card.warning {{ background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); }}
        .stat-card.info {{ background: linear-gradient(135deg, #30cfd0 0%, #330867 100%); }}
        .stat-card.success {{ background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); color: #333; }}
        .stat-value {{ font-size: 32px; font-weight: bold; margin: 10px 0; }}
        .stat-label {{ font-size: 14px; opacity: 0.9; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th {{ background: #2196F3; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #eee; }}
        tr:hover {{ background: #f5f5f5; }}
        .badge {{ display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }}
        .badge.critical {{ background: #f44336; color: white; }}
        .badge.high {{ background: #ff9800; color: white; }}
        .badge.medium {{ background: #ffeb3b; color: #333; }}
        .badge.low {{ background: #4caf50; color: white; }}
        .threat-score {{ font-weight: bold; }}
        .threat-score.critical {{ color: #f44336; }}
        .threat-score.high {{ color: #ff9800; }}
        .threat-score.medium {{ color: #ffeb3b; }}
        .threat-score.low {{ color: #4caf50; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>IPS安全分析报告</h1>
        <div class="meta">
            报告时间: {report.get("timestamp", "N/A")}<br>
            分析范围: {report.get("time_range", "N/A")}
        </div>

        <h2>概览统计</h2>
        <div class="stats-grid">
            <div class="stat-card critical">
                <div class="stat-label">总攻击次数</div>
                <div class="stat-value">{overview.get("total_attacks", 0)}</div>
            </div>
            <div class="stat-card warning">
                <div class="stat-label">高危事件</div>
                <div class="stat-value">{overview.get("high_risk_events", 0)}</div>
            </div>
            <div class="stat-card info">
                <div class="stat-label">活跃攻击源</div>
                <div class="stat-value">{overview.get("active_attackers", 0)}</div>
            </div>
            <div class="stat-card success">
                <div class="stat-label">防护成功率</div>
                <div class="stat-value">{overview.get("protection_rate", 0)}%</div>
            </div>
        </div>

        <h2>攻击类型分布</h2>
        <table>
            <tr><th>攻击类型</th><th>次数</th><th>占比</th></tr>
'''

        for attack_type in attack_types.get('distribution', [])[:10]:
            html += f'''            <tr>
                <td>{attack_type.get("attack_type", "N/A")}</td>
                <td>{attack_type.get("total", 0)}</td>
                <td>{attack_type.get("percentage", 0)}%</td>
            </tr>
'''

        html += '''        </table>

        <h2>TOP 攻击源</h2>
        <table>
            <tr><th>源IP</th><th>攻击次数</th><th>目标数量</th><th>威胁等级</th></tr>
'''

        for attacker in top_attackers[:10]:
            html += f'''            <tr>
                <td>{attacker.get("src_ip", "N/A")}</td>
                <td>{attacker.get("attack_count", 0)}</td>
                <td>{attacker.get("target_count", 0)}</td>
                <td><span class="threat-score {attacker.get("threat_level", "low")}">{attacker.get("threat_level", "N/A").upper()}</span></td>
            </tr>
'''

        html += '''        </table>

        <h2>TOP 被攻击目标</h2>
        <table>
            <tr><th>目标IP</th><th>端口</th><th>服务</th><th>攻击次数</th></tr>
'''

        for target in top_targets[:10]:
            html += f'''            <tr>
                <td>{target.get("dst_ip", "N/A")}</td>
                <td>{target.get("dst_port", "N/A")}</td>
                <td>{target.get("service", "N/A")}</td>
                <td>{target.get("attack_count", 0)}</td>
            </tr>
'''

        html += '''        </table>
    </div>
</body>
</html>'''

        return html


class WebServer:
    """Web服务器"""

    def __init__(self, host: str = '0.0.0.0', port: int = 8081):
        self.host = host
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        """启动Web服务器"""
        try:
            self.server = HTTPServer((self.host, self.port), WebHandler)
            self.thread = Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            logger.info(f"Web管理界面已启动: http://{self.host}:{self.port}")
        except Exception as e:
            logger.error(f"启动Web服务器失败: {e}")

    def stop(self):
        """停止Web服务器"""
        if self.server:
            self.server.shutdown()
            logger.info("Web服务器已停止")


# 全局Web服务器实例
web_server = None


def start_web_server(host: str = '0.0.0.0', port: int = 8081):
    """启动Web服务"""
    global web_server
    web_server = WebServer(host, port)
    web_server.start()


if __name__ == "__main__":
    # 测试代码
    import argparse

    parser = argparse.ArgumentParser(description='Web管理界面')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址')
    parser.add_argument('--port', type=int, default=8081, help='监听端口')
    args = parser.parse_args()

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 启动服务
    start_web_server(args.host, args.port)

    print(f"Web管理界面已启动: http://{args.host}:{args.port}")
    print("按 Ctrl+C 停止服务")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        if web_server:
            web_server.stop()
        print("服务已停止")
