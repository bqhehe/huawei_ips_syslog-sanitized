#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
通知配置管理模块
支持企业微信、钉钉、飞书等多种通知方式
"""

import sys
import os
import json
import logging
import requests
import hashlib
import time
import hmac
import base64
import urllib.parse
from typing import Dict, List, Optional
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)

# 通知配置文件路径
NOTIFICATION_CONFIG_FILE = "data/notification_config.json"


class NotificationConfig:
    """通知配置管理类"""

    def __init__(self):
        self.config_file = Path(BASE_DIR) / NOTIFICATION_CONFIG_FILE
        self.config: Dict = self._load_config()

    def _load_config(self) -> Dict:
        """加载通知配置"""
        default_config = {
            "enabled_channels": ["wechat"],  # 启用的通知渠道
            "wechat": {
                "enabled": True,
                "webhook_url": Config.WECHAT_WEBHOOK_URL
            },
            "dingtalk": {
                "enabled": False,
                "webhook_url": "",
                "sign_secret": ""
            },
            "feishu": {
                "enabled": False,
                "webhook_url": "",
                "sign_secret": ""
            },
            "email": {
                "enabled": False,
                "smtp_host": Config.MAIL_HOST,
                "smtp_user": Config.MAIL_USER,
                "smtp_password": Config.MAIL_PASSWORD,
                "sender": Config.MAIL_SENDER,
                "recipients": Config.MAIL_RECEIVERS
            }
        }

        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # 合并配置，确保所有字段都存在
                    for key in default_config:
                        if key not in loaded:
                            loaded[key] = default_config[key]
                        elif isinstance(default_config[key], dict):
                            for sub_key in default_config[key]:
                                if sub_key not in loaded[key]:
                                    loaded[key][sub_key] = default_config[key][sub_key]
                    return loaded
            except Exception as e:
                logger.error(f"加载通知配置失败: {e}")

        return default_config

    def _save_config(self) -> bool:
        """保存通知配置"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"保存通知配置失败: {e}")
            return False

    def get_config(self) -> Dict:
        """获取通知配置"""
        return self.config.copy()

    def update_channel(self, channel: str, enabled: bool, **kwargs) -> bool:
        """
        更新通知渠道配置

        Args:
            channel: 渠道名称 (wechat, dingtalk, feishu, email)
            enabled: 是否启用
            **kwargs: 其他配置参数
        """
        if channel not in self.config:
            logger.error(f"不支持的通知渠道: {channel}")
            return False

        self.config[channel]['enabled'] = enabled

        # 更新其他参数
        for key, value in kwargs.items():
            if value is not None and value != '':
                self.config[channel][key] = value

        # 更新启用的渠道列表
        if enabled and channel not in self.config['enabled_channels']:
            self.config['enabled_channels'].append(channel)
        elif not enabled and channel in self.config['enabled_channels']:
            self.config['enabled_channels'].remove(channel)

        return self._save_config()

    def test_channel(self, channel: str) -> Dict:
        """
        测试通知渠道

        Args:
            channel: 渠道名称

        Returns:
            Dict: 测试结果 {success: bool, message: str}
        """
        if channel == 'wechat':
            return self._test_wechat()
        elif channel == 'dingtalk':
            return self._test_dingtalk()
        elif channel == 'feishu':
            return self._test_feishu()
        elif channel == 'email':
            return self._test_email()
        else:
            return {'success': False, 'message': f'不支持的渠道: {channel}'}

    def _test_wechat(self) -> Dict:
        """测试企业微信通知"""
        try:
            webhook_url = self.config['wechat'].get('webhook_url')
            if not webhook_url or webhook_url == 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your_webhook_key_here':
                return {'success': False, 'message': '请先配置企业微信webhook URL'}

            message_data = {
                "msgtype": "text",
                "text": {
                    "content": "【测试消息】IPS Syslog 自动响应系统通知测试"
                }
            }

            response = requests.post(
                webhook_url,
                json=message_data,
                timeout=10
            )
            result = response.json()

            if result.get('errcode') == 0:
                return {'success': True, 'message': '企业微信通知发送成功'}
            else:
                return {'success': False, 'message': f"企业微信通知失败: {result.get('errmsg', 'Unknown error')}"}

        except Exception as e:
            return {'success': False, 'message': f'测试失败: {str(e)}'}

    def _test_dingtalk(self) -> Dict:
        """测试钉钉通知"""
        try:
            webhook_url = self.config['dingtalk'].get('webhook_url')
            if not webhook_url:
                return {'success': False, 'message': '请先配置钉钉webhook URL'}

            message_data = {
                "msgtype": "text",
                "text": {
                    "content": "【测试消息】IPS Syslog 自动响应系统通知测试"
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
                hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
                sign = urllib.parse.quote(base64.b64encode(hmac_code))
                message_data['timestamp'] = timestamp
                message_data['sign'] = sign

            response = requests.post(
                webhook_url,
                json=message_data,
                timeout=10
            )
            result = response.json()

            if result.get('errcode') == 0:
                return {'success': True, 'message': '钉钉通知发送成功'}
            else:
                return {'success': False, 'message': f"钉钉通知失败: {result.get('errmsg', 'Unknown error')}"}

        except Exception as e:
            return {'success': False, 'message': f'测试失败: {str(e)}'}

    def _test_feishu(self) -> Dict:
        """测试飞书通知"""
        try:
            webhook_url = self.config['feishu'].get('webhook_url')
            if not webhook_url:
                return {'success': False, 'message': '请先配置飞书webhook URL'}

            message_data = {
                "msg_type": "text",
                "content": {
                    "text": "【测试消息】IPS Syslog 自动响应系统通知测试"
                }
            }

            response = requests.post(
                webhook_url,
                json=message_data,
                timeout=10
            )
            result = response.json()

            if result.get('code') == 0:
                return {'success': True, 'message': '飞书通知发送成功'}
            else:
                return {'success': False, 'message': f"飞书通知失败: {result.get('msg', 'Unknown error')}"}

        except Exception as e:
            return {'success': False, 'message': f'测试失败: {str(e)}'}

    def _test_email(self) -> Dict:
        """测试邮件通知"""
        try:
            import smtplib
            from email.mime.text import MIMEText

            smtp_host = self.config['email'].get('smtp_host')
            smtp_user = self.config['email'].get('smtp_user')
            smtp_password = self.config['email'].get('smtp_password')
            sender = self.config['email'].get('sender')
            recipients = self.config['email'].get('recipients', [])

            if not all([smtp_host, smtp_user, smtp_password, sender]):
                return {'success': False, 'message': '请先配置邮件相关参数'}

            if not recipients:
                return {'success': False, 'message': '请先配置收件人'}

            msg = MIMEText('【测试消息】IPS Syslog 自动响应系统通知测试', 'plain', 'utf-8')
            msg['From'] = sender
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = 'IPS Syslog 测试消息'

            with smtplib.SMTP(smtp_host, 25, timeout=10) as smtp:
                smtp.login(smtp_user, smtp_password)
                smtp.sendmail(sender, recipients, msg.as_string())

            return {'success': True, 'message': '邮件通知发送成功'}

        except Exception as e:
            return {'success': False, 'message': f'测试失败: {str(e)}'}


# 全局通知配置实例
notification_config = NotificationConfig()


if __name__ == '__main__':
    # 测试代码
    config = notification_config.get_config()
    print(json.dumps(config, indent=2, ensure_ascii=False))
