#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统一通知发送模块
支持企业微信、钉钉、飞书、邮件等多种通知方式
支持重试机制和模板渲染
"""

import sys
import os
import json
import logging
import requests
import smtplib
import time
from email.mime.text import MIMEText
from email.header import Header
from typing import List, Dict, Optional, Any

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from notification.notification_templates import render_ips_alert, render_test_message, notification_templates

logger = logging.getLogger(__name__)


class NotificationSender:
    """统一通知发送类"""

    # 重试配置
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # 初始重试延迟(秒)
    RETRY_BACKOFF = 2  # 指数退避倍数

    def __init__(self):
        """初始化通知发送器"""
        self.config = self._load_notification_config()

    def _load_notification_config(self) -> Dict:
        """加载通知配置"""
        config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data/notification_config.json')

        default_config = {
            'enabled_channels': ['wechat'],
            'wechat': {'enabled': True, 'webhook_url': Config.WECHAT_WEBHOOK_URL},
            'dingtalk': {'enabled': False, 'webhook_url': '', 'sign_secret': ''},
            'feishu': {'enabled': False, 'webhook_url': '', 'sign_secret': ''},
            'email': {
                'enabled': False,
                'smtp_host': Config.MAIL_HOST,
                'smtp_user': Config.MAIL_USER,
                'smtp_password': Config.MAIL_PASSWORD,
                'sender': Config.MAIL_SENDER,
                'recipients': Config.MAIL_RECEIVERS
            }
        }

        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # 合并配置
                    for key in default_config:
                        if key not in loaded:
                            loaded[key] = default_config[key]
                    return loaded
            except Exception as e:
                logger.error(f"加载通知配置失败: {e}")

        return default_config

    def _retry_with_backoff(self, func, *args, **kwargs) -> bool:
        """
        带指数退避的重试机制

        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数

        Returns:
            bool: 是否成功
        """
        delay = self.RETRY_DELAY
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except (requests.RequestException, requests.Timeout, smtplib.SMTPException) as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(f"通知发送失败，{delay}秒后重试 (尝试 {attempt + 1}/{self.MAX_RETRIES}): {e}")
                    time.sleep(delay)
                    delay *= self.RETRY_BACKOFF
                else:
                    logger.error(f"通知发送失败，已达最大重试次数: {e}")

        logger.error(f"重试失败: {last_error}")
        return False

    def send_ips_alert(self, src_ip: str, dst_ip: str, detect_time: str,
                       attack_type: str, severity: str, action: str = "N/A",
                       rule_name: str = None) -> Dict[str, bool]:
        """
        发送IPS告警通知（使用模板）

        Args:
            src_ip: 源IP地址
            dst_ip: 目标IP地址
            detect_time: 检测时间
            attack_type: 攻击类型
            severity: 严重性
            action: 处理动作
            rule_name: 规则名称

        Returns:
            Dict: 各渠道的发送结果 {channel: success}
        """
        results = {}
        enabled_channels = self.config.get('enabled_channels', [])

        if not enabled_channels:
            logger.warning("没有启用任何通知渠道")
            return {'all': False}

        for channel in enabled_channels:
            try:
                # 使用模板渲染消息
                subject, content = render_ips_alert(
                    channel=channel,
                    src_ip=src_ip,
                    dst_ip=dst_ip,
                    detect_time=detect_time,
                    attack_type=attack_type,
                    severity=severity,
                    action=action,
                    rule_name=rule_name
                )

                # 根据渠道发送
                if channel == 'wechat':
                    results['wechat'] = self._retry_with_backoff(self._send_wechat, content, None)
                elif channel == 'dingtalk':
                    results['dingtalk'] = self._retry_with_backoff(self._send_dingtalk, content)
                elif channel == 'feishu':
                    results['feishu'] = self._retry_with_backoff(self._send_feishu, content)
                elif channel == 'email':
                    results['email'] = self._retry_with_backoff(self._send_email_with_subject, content, subject)
                else:
                    logger.warning(f"不支持的通知渠道: {channel}")
                    results[channel] = False
            except Exception as e:
                logger.error(f"发送{channel}通知失败: {e}")
                results[channel] = False

        return results

    def send_notification(self, message: str, mentioned_list: List[str] = None) -> Dict[str, bool]:
        """
        发送通知到所有启用的渠道

        Args:
            message: 消息内容
            mentioned_list: 需要@的用户列表（手机号或邮箱）

        Returns:
            Dict: 各渠道的发送结果 {channel: success}
        """
        results = {}
        enabled_channels = self.config.get('enabled_channels', [])

        if not enabled_channels:
            logger.warning("没有启用任何通知渠道")
            return {'all': False}

        for channel in enabled_channels:
            try:
                if channel == 'wechat':
                    results['wechat'] = self._retry_with_backoff(self._send_wechat, message, mentioned_list)
                elif channel == 'dingtalk':
                    results['dingtalk'] = self._retry_with_backoff(self._send_dingtalk, message)
                elif channel == 'feishu':
                    results['feishu'] = self._retry_with_backoff(self._send_feishu, message)
                elif channel == 'email':
                    results['email'] = self._retry_with_backoff(self._send_email, message)
                else:
                    logger.warning(f"不支持的通知渠道: {channel}")
                    results[channel] = False
            except Exception as e:
                logger.error(f"发送{channel}通知失败: {e}")
                results[channel] = False

        return results

    def _send_wechat(self, message: str, mentioned_list: List[str] = None) -> bool:
        """发送企业微信通知"""
        try:
            webhook_url = self.config['wechat'].get('webhook_url')
            if not webhook_url:
                logger.warning("企业微信webhook未配置")
                return False

            message_data = {
                "msgtype": "text",
                "text": {
                    "content": message
                }
            }

            if mentioned_list:
                message_data["text"]["mentioned_mobile_list"] = mentioned_list

            response = requests.post(webhook_url, json=message_data, timeout=10)
            result = response.json()

            if result.get('errcode') == 0:
                logger.info("企业微信通知发送成功")
                return True
            else:
                logger.error(f"企业微信通知失败: {result}")
                return False

        except Exception as e:
            logger.error(f"企业微信通知发送异常: {e}")
            return False

    def _send_dingtalk(self, message: str) -> bool:
        """发送钉钉通知"""
        try:
            webhook_url = self.config['dingtalk'].get('webhook_url')
            if not webhook_url:
                logger.warning("钉钉webhook未配置")
                return False

            message_data = {
                "msgtype": "text",
                "text": {
                    "content": message
                }
            }

            # 如果有签名密钥，添加签名
            sign_secret = self.config['dingtalk'].get('sign_secret')
            if sign_secret:
                import time
                import hmac
                import base64
                import urllib.parse

                timestamp = str(round(time.time() * 1000))
                secret_enc = sign_secret.encode('utf-8')
                string_to_sign = f'{timestamp}\n{sign_secret}'
                string_to_sign_enc = string_to_sign.encode('utf-8')
                hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod='sha256').digest()
                sign = urllib.parse.quote(base64.b64encode(hmac_code))
                message_data['timestamp'] = timestamp
                message_data['sign'] = sign

            response = requests.post(webhook_url, json=message_data, timeout=10)
            result = response.json()

            if result.get('errcode') == 0:
                logger.info("钉钉通知发送成功")
                return True
            else:
                logger.error(f"钉钉通知失败: {result}")
                return False

        except Exception as e:
            logger.error(f"钉钉通知发送异常: {e}")
            return False

    def _send_feishu(self, message: str) -> bool:
        """发送飞书通知"""
        try:
            webhook_url = self.config['feishu'].get('webhook_url')
            if not webhook_url:
                logger.warning("飞书webhook未配置")
                return False

            message_data = {
                "msg_type": "text",
                "content": {
                    "text": message
                }
            }

            response = requests.post(webhook_url, json=message_data, timeout=10)
            result = response.json()

            if result.get('code') == 0:
                logger.info("飞书通知发送成功")
                return True
            else:
                logger.error(f"飞书通知失败: {result}")
                return False

        except Exception as e:
            logger.error(f"飞书通知发送异常: {e}")
            return False

    def _send_email(self, message: str) -> bool:
        """发送邮件通知"""
        return self._send_email_with_subject(message, 'IPS Syslog 威胁防护告警')

    def _send_email_with_subject(self, message: str, subject: str) -> bool:
        """发送带主题的邮件通知"""
        try:
            smtp_host = self.config['email'].get('smtp_host')
            smtp_user = self.config['email'].get('smtp_user')
            smtp_password = self.config['email'].get('smtp_password')
            sender = self.config['email'].get('sender')
            recipients = self.config['email'].get('recipients', [])

            if not all([smtp_host, smtp_user, smtp_password, sender]):
                logger.warning("邮件配置不完整，跳过发送")
                return False

            if not recipients:
                logger.warning("邮件收件人为空，跳过发送")
                return False

            # 构建邮件
            msg = MIMEText(message, 'plain', 'utf-8')
            msg['From'] = sender
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = Header(subject, 'utf-8')

            # 发送邮件
            with smtplib.SMTP(smtp_host, 25, timeout=30) as smtp:
                smtp.login(smtp_user, smtp_password)
                smtp.sendmail(sender, recipients, msg.as_string())

            logger.info("邮件通知发送成功")
            return True

        except smtplib.SMTPException as e:
            # 抛出SMTP异常以便重试机制工作
            raise
        except Exception as e:
            logger.error(f"邮件通知发送异常: {e}")
            return False

    def reload_config(self):
        """重新加载配置"""
        self.config = self._load_notification_config()
        notification_templates.reload()
        logger.info("通知配置和模板已重新加载")


# 全局通知发送器实例
notification_sender = NotificationSender()


# 兼容旧接口
def send_wechat_message(text: str, mentioned_mobile_list: List[str] = None) -> bool:
    """发送企业微信消息（兼容旧接口）"""
    return notification_sender._send_wechat(text, mentioned_mobile_list)


def send_all_notifications(message: str, mentioned_list: List[str] = None) -> Dict[str, bool]:
    """
    发送通知到所有启用的渠道

    Args:
        message: 消息内容
        mentioned_list: 需要@的用户列表

    Returns:
        Dict: 各渠道的发送结果
    """
    return notification_sender.send_notification(message, mentioned_list)


def send_ips_alert_notification(src_ip: str, dst_ip: str, detect_time: str,
                                 attack_type: str, severity: str, action: str = "N/A",
                                 rule_name: str = None) -> Dict[str, bool]:
    """
    发送IPS告警通知（使用模板）

    Args:
        src_ip: 源IP地址
        dst_ip: 目标IP地址
        detect_time: 检测时间
        attack_type: 攻击类型
        severity: 严重性
        action: 处理动作
        rule_name: 规则名称

    Returns:
        Dict: 各渠道的发送结果
    """
    return notification_sender.send_ips_alert(
        src_ip=src_ip,
        dst_ip=dst_ip,
        detect_time=detect_time,
        attack_type=attack_type,
        severity=severity,
        action=action,
        rule_name=rule_name
    )


def send_test_notification(channel: str = None) -> Dict[str, bool]:
    """
    发送测试通知

    Args:
        channel: 指定渠道，如果为None则发送到所有启用的渠道

    Returns:
        Dict: 各渠道的发送结果
    """
    if channel:
        # 发送到指定渠道
        subject, content = render_test_message(channel)
        if channel == 'wechat':
            return {'wechat': notification_sender._retry_with_backoff(notification_sender._send_wechat, content, None)}
        elif channel == 'dingtalk':
            return {'dingtalk': notification_sender._retry_with_backoff(notification_sender._send_dingtalk, content)}
        elif channel == 'feishu':
            return {'feishu': notification_sender._retry_with_backoff(notification_sender._send_feishu, content)}
        elif channel == 'email':
            return {'email': notification_sender._retry_with_backoff(notification_sender._send_email_with_subject, content, subject)}
        else:
            return {channel: False}
    else:
        # 发送到所有启用的渠道
        enabled_channels = notification_sender.config.get('enabled_channels', [])
        results = {}
        for ch in enabled_channels:
            subject, content = render_test_message(ch)
            if ch == 'wechat':
                results[ch] = notification_sender._retry_with_backoff(notification_sender._send_wechat, content, None)
            elif ch == 'dingtalk':
                results[ch] = notification_sender._retry_with_backoff(notification_sender._send_dingtalk, content)
            elif ch == 'feishu':
                results[ch] = notification_sender._retry_with_backoff(notification_sender._send_feishu, content)
            elif ch == 'email':
                results[ch] = notification_sender._retry_with_backoff(notification_sender._send_email_with_subject, content, subject)
        return results


if __name__ == '__main__':
    # 测试代码
    print("=== 测试通知发送功能 ===")

    # 测试原始消息发送
    print("\n--- 测试原始消息发送 ---")
    test_message = """防火墙威胁防护告警
攻击源IP: 8.8.8.8
目的地址: 192.168.1.1
攻击时间: 2026-02-28 12:00:00
攻击类型: Directory Traversal
严重性: medium"""

    results = send_all_notifications(test_message)
    print("发送结果:", results)

    # 测试模板消息发送
    print("\n--- 测试IPS告警模板发送 ---")
    results = send_ips_alert_notification(
        src_ip="8.8.8.8",
        dst_ip="192.168.1.1",
        detect_time="2026-02-28 12:00:00",
        attack_type="Directory Traversal",
        severity="high",
        action="Block",
        rule_name="block_high_severity"
    )
    print("发送结果:", results)
