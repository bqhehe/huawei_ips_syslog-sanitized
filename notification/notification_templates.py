#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
通知模板模块
支持可自定义的通知消息模板
"""

import json
import os
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class NotificationTemplates:
    """通知模板管理类"""

    # 默认模板
    DEFAULT_TEMPLATES = {
        "ips_alert": {
            "name": "IPS告警通知",
            "description": "IPS入侵检测告警通知模板",
            "channels": {
                "wechat": {
                    "enabled": True,
                    "template": """【IPS威胁防护告警】
🚨 攻击源IP: {src_ip}
🎯 目标地址: {dst_ip}
⏰ 检测时间: {detect_time}
🔍 攻击类型: {attack_type}
⚠️ 严重性: {severity}
🛡️ 处理动作: {action}
{rule_section}
---
来源: 防火墙 IPS自动响应系统"""
                },
                "dingtalk": {
                    "enabled": True,
                    "template": """## IPS威胁防护告警

> **攻击源IP**: {src_ip}
> **目标地址**: {dst_ip}
> **检测时间**: {detect_time}
> **攻击类型**: {attack_type}
> **严重性**: {severity}
> **处理动作**: {action}
{rule_section}

---
_防火墙 IPS自动响应系统_"""
                },
                "feishu": {
                    "enabled": True,
                    "template": """【IPS威胁防护告警】
攻击源IP: {src_ip}
目标地址: {dst_ip}
检测时间: {detect_time}
攻击类型: {attack_type}
严重性: {severity}
处理动作: {action}
{rule_section}
---
防火墙 IPS自动响应系统"""
                },
                "email": {
                    "enabled": True,
                    "subject": "【告警】IPS威胁防护 - {attack_type}",
                    "template": """尊敬的用户：

IPS入侵检测系统检测到威胁攻击，详细信息如下：

【攻击源IP】{src_ip}
【目标地址】{dst_ip}
【检测时间】{detect_time}
【攻击类型】{attack_type}
【严重性】{severity}
【处理动作】{action}
{rule_section}

---
此邮件由IPS自动响应系统发送，请勿回复。
防火墙 IPS自动响应系统
{timestamp}"""
                }
            }
        },
        "system_alert": {
            "name": "系统告警通知",
            "description": "系统异常或重要事件通知",
            "channels": {
                "wechat": {
                    "enabled": True,
                    "template": """【系统告警】
⚠️ {title}
📝 {message}
⏰ {time}
---
IPS自动响应系统"""
                },
                "dingtalk": {
                    "enabled": True,
                    "template": """## 系统告警

**{title}**

{message}

---
_时间: {time}_"""
                },
                "feishu": {
                    "enabled": True,
                    "template": """【系统告警】
{title}
{message}
时间: {time}
---
IPS自动响应系统"""
                },
                "email": {
                    "enabled": True,
                    "subject": "【系统告警】{title}",
                    "template": """尊敬的用户：

系统发生告警事件：

【告警标题】{title}
【告警内容】{message}
【发生时间】{time}

---
IPS自动响应系统
{timestamp}"""
                }
            }
        },
        "test_message": {
            "name": "测试消息",
            "description": "用于测试通知配置的测试消息",
            "channels": {
                "wechat": {
                    "enabled": True,
                    "template": """【测试消息】
这是一条测试消息，用于验证通知配置是否正确。

如果您收到此消息，说明通知配置正常！
---
IPS自动响应系统 {timestamp}"""
                },
                "dingtalk": {
                    "enabled": True,
                    "template": """## 测试消息

这是一条测试消息，用于验证通知配置是否正确。

---
_{timestamp}_"""
                },
                "feishu": {
                    "enabled": True,
                    "template": """【测试消息】
这是一条测试消息，用于验证通知配置是否正确。

---
IPS自动响应系统 {timestamp}"""
                },
                "email": {
                    "enabled": True,
                    "subject": "【测试】通知配置测试",
                    "template": """尊敬的用户：

这是一封测试邮件，用于验证邮件通知配置是否正确。

如果您收到此邮件，说明邮件通知配置正常！

---
IPS自动响应系统
{timestamp}"""
                }
            }
        }
    }

    # 严重性级别对应的emoji和颜色
    SEVERITY_MAP = {
        "critical": {"emoji": "🔴", "label": "严重"},
        "high": {"emoji": "🟠", "label": "高"},
        "medium": {"emoji": "🟡", "label": "中"},
        "low": {"emoji": "🟢", "label": "低"},
        "info": {"emoji": "🔵", "label": "信息"}
    }

    def __init__(self, template_file: Optional[str] = None):
        """初始化模板管理器"""
        self.template_file = template_file or self._get_default_template_file()
        self.templates = self._load_templates()

    def _get_default_template_file(self) -> str:
        """获取默认模板文件路径"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, 'data', 'notification_templates.json')

    def _load_templates(self) -> dict:
        """加载模板配置"""
        if os.path.exists(self.template_file):
            try:
                with open(self.template_file, 'r', encoding='utf-8') as f:
                    custom_templates = json.load(f)
                    # 合并自定义模板和默认模板
                    templates = self.DEFAULT_TEMPLATES.copy()
                    templates.update(custom_templates)
                    return templates
            except Exception as e:
                logger.error(f"加载通知模板失败: {e}")
        return self.DEFAULT_TEMPLATES.copy()

    def _save_templates(self):
        """保存模板配置"""
        try:
            os.makedirs(os.path.dirname(self.template_file), exist_ok=True)
            with open(self.template_file, 'w', encoding='utf-8') as f:
                json.dump(self.templates, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存通知模板失败: {e}")

    def render(self, template_type: str, channel: str, **kwargs) -> tuple:
        """
        渲染通知消息

        Args:
            template_type: 模板类型 (ips_alert, system_alert, test_message)
            channel: 通知渠道 (wechat, dingtalk, feishu, email)
            **kwargs: 模板变量

        Returns:
            tuple: (subject, content) 对于邮件，其他渠道返回 (None, content)
        """
        # 获取模板
        template = self.get_template(template_type, channel)
        if not template:
            logger.warning(f"模板不存在: {template_type}/{channel}")
            return self._render_fallback(template_type, channel, **kwargs)

        try:
            # 添加默认变量
            kwargs.setdefault('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

            # 处理严重性
            if 'severity' in kwargs:
                severity_info = self.SEVERITY_MAP.get(kwargs['severity'].lower(), {})
                if severity_info:
                    kwargs.setdefault('severity_emoji', severity_info.get('emoji', ''))
                    kwargs.setdefault('severity_label', severity_info.get('label', kwargs['severity']))

            # 格式化严重性显示
            if 'severity' in kwargs and 'severity_emoji' in kwargs:
                kwargs['severity'] = f"{kwargs['severity_emoji']} {kwargs['severity']}"

            # 处理规则部分
            rule_section = ""
            if kwargs.get('rule_name') and kwargs.get('rule_name') != 'default':
                rule_section = f"\n📋 处理规则: {kwargs['rule_name']}"
            kwargs['rule_section'] = rule_section

            # 渲染模板
            if channel == 'email':
                subject = template.get('subject', 'IPS通知').format(**kwargs)
                content = template['template'].format(**kwargs)
                return (subject, content)
            else:
                content = template['template'].format(**kwargs)
                return (None, content)

        except KeyError as e:
            logger.error(f"模板变量缺失: {e}")
            return self._render_fallback(template_type, channel, **kwargs)
        except Exception as e:
            logger.error(f"渲染模板失败: {e}")
            return self._render_fallback(template_type, channel, **kwargs)

    def _render_fallback(self, template_type: str, channel: str, **kwargs) -> tuple:
        """回退渲染方法"""
        if template_type == 'ips_alert':
            content = (
                f"防火墙威胁防护告警\n"
                f"攻击源IP: {kwargs.get('src_ip', 'N/A')}\n"
                f"目的地址: {kwargs.get('dst_ip', 'N/A')}\n"
                f"攻击时间: {kwargs.get('detect_time', 'N/A')}\n"
            )
            if kwargs.get('attack_type'):
                content += f"攻击类型: {kwargs['attack_type']}\n"
            if kwargs.get('severity'):
                content += f"严重性: {kwargs['severity']}\n"
            if kwargs.get('action'):
                content += f"动作: {kwargs['action']}\n"

            if channel == 'email':
                return (f"【告警】IPS威胁防护", content)
            return (None, content)

        elif template_type == 'test_message':
            content = f"【测试消息】通知配置测试\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            if channel == 'email':
                return ("【测试】通知配置测试", content)
            return (None, content)

        return (None, str(kwargs))

    def get_template(self, template_type: str, channel: str) -> Optional[dict]:
        """获取指定模板"""
        return self.templates.get(template_type, {}).get('channels', {}).get(channel)

    def update_template(self, template_type: str, channel: str, template: str, subject: Optional[str] = None) -> bool:
        """更新模板"""
        try:
            if template_type not in self.templates:
                self.templates[template_type] = {
                    "name": template_type,
                    "description": f"{template_type}模板",
                    "channels": {}
                }

            if 'channels' not in self.templates[template_type]:
                self.templates[template_type]['channels'] = {}

            if channel not in self.templates[template_type]['channels']:
                self.templates[template_type]['channels'][channel] = {}

            self.templates[template_type]['channels'][channel]['template'] = template
            self.templates[template_type]['channels'][channel]['enabled'] = True

            if subject:
                self.templates[template_type]['channels'][channel]['subject'] = subject

            self._save_templates()
            return True
        except Exception as e:
            logger.error(f"更新模板失败: {e}")
            return False

    def list_templates(self) -> dict:
        """列出所有模板"""
        return {
            name: {
                "name": tmpl.get("name"),
                "description": tmpl.get("description"),
                "channels": list(tmpl.get("channels", {}).keys())
            }
            for name, tmpl in self.templates.items()
        }

    def reload(self):
        """重新加载模板"""
        self.templates = self._load_templates()


# 全局模板实例
notification_templates = NotificationTemplates()


def render_ips_alert(channel: str, src_ip: str, dst_ip: str, detect_time: str,
                     attack_type: str, severity: str, action: str = "N/A",
                     rule_name: str = None) -> tuple:
    """
    渲染IPS告警通知

    Args:
        channel: 通知渠道
        src_ip: 源IP
        dst_ip: 目标IP
        detect_time: 检测时间
        attack_type: 攻击类型
        severity: 严重性
        action: 处理动作
        rule_name: 规则名称

    Returns:
        tuple: (subject, content)
    """
    return notification_templates.render(
        'ips_alert',
        channel,
        src_ip=src_ip,
        dst_ip=dst_ip,
        detect_time=detect_time,
        attack_type=attack_type,
        severity=severity,
        action=action,
        rule_name=rule_name
    )


def render_test_message(channel: str) -> tuple:
    """渲染测试消息"""
    return notification_templates.render('test_message', channel)


if __name__ == '__main__':
    # 测试代码
    print("=== 测试IPS告警模板 ===")
    for channel in ['wechat', 'dingtalk', 'feishu', 'email']:
        print(f"\n--- {channel} ---")
        subject, content = render_ips_alert(
            channel=channel,
            src_ip="8.8.8.8",
            dst_ip="192.168.1.1",
            detect_time="2026-02-28 12:00:00",
            attack_type="Directory Traversal",
            severity="high",
            action="Block",
            rule_name="block_high_severity"
        )
        if subject:
            print(f"Subject: {subject}")
        print(f"Content:\n{content}")
