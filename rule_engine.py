#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
规则引擎模块
根据攻击类型、严重性等条件执行不同的处理策略
"""

import sys
import os
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config

logger = logging.getLogger(__name__)


class Action(Enum):
    """处理动作"""
    BLOCK = "block"           # 封禁IP
    ALERT_ONLY = "alert_only" # 仅告警不封禁
    IGNORE = "ignore"         # 忽略


class Severity(Enum):
    """严重性等级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Rule:
    """规则"""
    name: str
    description: str
    attack_types: List[str]  # 攻击类型列表
    severity: Severity       # 严重性
    action: Action           # 处理动作
    expire_hours: int = 24   # 黑名单过期时间（小时）


class RuleEngine:
    """规则引擎"""

    def __init__(self):
        self.rules: List[Rule] = []
        self._load_default_rules()

    def _load_default_rules(self):
        """加载默认规则"""
        self.rules = [
            # 高严重性攻击 - 立即封禁，48小时
            Rule(
                name="critical_attack",
                description="严重攻击，立即封禁48小时",
                attack_types=["*"],  # 匹配所有攻击类型
                severity=Severity.CRITICAL,
                action=Action.BLOCK,
                expire_hours=48
            ),

            # 高严重性攻击 - 立即封禁，24小时
            Rule(
                name="high_severity_attack",
                description="高严重性攻击，立即封禁24小时",
                attack_types=["*"],
                severity=Severity.HIGH,
                action=Action.BLOCK,
                expire_hours=24
            ),

            # 中等严重性攻击 - 封禁12小时
            Rule(
                name="medium_severity_attack",
                description="中等严重性攻击，封禁12小时",
                attack_types=["*"],
                severity=Severity.MEDIUM,
                action=Action.BLOCK,
                expire_hours=12
            ),

            # 低严重性攻击 - 仅告警不封禁
            Rule(
                name="low_severity_attack",
                description="低严重性攻击，仅告警不封禁",
                attack_types=["*"],
                severity=Severity.LOW,
                action=Action.ALERT_ONLY,
                expire_hours=0
            ),

            # 信息级别 - 忽略
            Rule(
                name="info_level_attack",
                description="信息级别，忽略",
                attack_types=["*"],
                severity=Severity.INFO,
                action=Action.IGNORE,
                expire_hours=0
            ),

            # 特定攻击类型 - 挖矿攻击 - 立即封禁72小时
            Rule(
                name="mining_attack",
                description="挖矿攻击，立即封禁72小时",
                attack_types=["Mining Pool", "Crypto", "Mining"],
                severity=Severity.HIGH,
                action=Action.BLOCK,
                expire_hours=72
            ),

            # 特定攻击类型 - 暴力破解 - 立即封禁48小时
            Rule(
                name="brute_force_attack",
                description="暴力破解攻击，立即封禁48小时",
                attack_types=["Brute Force", "SSH Brute", "FTP Brute"],
                severity=Severity.HIGH,
                action=Action.BLOCK,
                expire_hours=48
            ),

            # 特定攻击类型 - 扫描探测 - 仅告警不封禁
            Rule(
                name="scan_attack",
                description="扫描探测，仅告警不封禁",
                attack_types=["Port Scan", "Nmap", "Network Scan"],
                severity=Severity.LOW,
                action=Action.ALERT_ONLY,
                expire_hours=0
            ),
        ]

        logger.info(f"加载了 {len(self.rules)} 条默认规则")

    def match_rule(self, attack_type: str, severity: str) -> Optional[Rule]:
        """
        匹配规则

        Args:
            attack_type: 攻击类型
            severity: 严重性

        Returns:
            Optional[Rule]: 匹配的规则，如果没有匹配则返回None
        """
        # 转换严重性
        try:
            severity_enum = Severity(severity.lower())
        except ValueError:
            severity_enum = Severity.MEDIUM  # 默认中等严重性

        # 优先匹配特定攻击类型的规则
        for rule in self.rules:
            if rule.action != Action.IGNORE:  # 跳过忽略规则
                for pattern in rule.attack_types:
                    if pattern != "*" and pattern.lower() in attack_type.lower():
                        if rule.severity == severity_enum:
                            return rule

        # 匹配严重性级别的规则
        for rule in self.rules:
            if rule.severity == severity_enum and rule.action != Action.IGNORE:
                return rule

        # 默认规则：中等严重性，封禁24小时
        return Rule(
            name="default",
            description="默认规则",
            attack_types=["*"],
            severity=Severity.MEDIUM,
            action=Action.BLOCK,
            expire_hours=24
        )

    def should_block(self, attack_type: str, severity: str) -> bool:
        """
        判断是否应该封禁

        Args:
            attack_type: 攻击类型
            severity: 严重性

        Returns:
            bool: 是否应该封禁
        """
        rule = self.match_rule(attack_type, severity)
        return rule.action == Action.BLOCK

    def should_alert(self, attack_type: str, severity: str) -> bool:
        """
        判断是否应该告警

        Args:
            attack_type: 攻击类型
            severity: 严重性

        Returns:
            bool: 是否应该告警
        """
        rule = self.match_rule(attack_type, severity)
        return rule.action != Action.IGNORE

    def get_expire_hours(self, attack_type: str, severity: str) -> int:
        """
        获取黑名单过期时间

        Args:
            attack_type: 攻击类型
            severity: 严重性

        Returns:
            int: 过期时间（小时）
        """
        rule = self.match_rule(attack_type, severity)
        return rule.expire_hours

    def get_rule_name(self, attack_type: str, severity: str) -> str:
        """
        获取匹配的规则名称

        Args:
            attack_type: 攻击类型
            severity: 严重性

        Returns:
            str: 规则名称
        """
        rule = self.match_rule(attack_type, severity)
        return rule.name

    def list_rules(self) -> List[Dict]:
        """
        列出所有规则

        Returns:
            List[Dict]: 规则列表
        """
        return [
            {
                'name': rule.name,
                'description': rule.description,
                'attack_types': rule.attack_types,
                'severity': rule.severity.value,
                'action': rule.action.value,
                'expire_hours': rule.expire_hours
            }
            for rule in self.rules
        ]


# 全局规则引擎实例
rule_engine = RuleEngine()


if __name__ == "__main__":
    # 测试代码
    import argparse

    parser = argparse.ArgumentParser(description='规则引擎测试工具')
    parser.add_argument('action', choices=['test', 'list'], help='操作类型')
    parser.add_argument('--attack-type', default='test', help='攻击类型')
    parser.add_argument('--severity', default='high', help='严重性')
    args = parser.parse_args()

    if args.action == 'test':
        should_block = rule_engine.should_block(args.attack_type, args.severity)
        should_alert = rule_engine.should_alert(args.attack_type, args.severity)
        expire_hours = rule_engine.get_expire_hours(args.attack_type, args.severity)
        rule_name = rule_engine.get_rule_name(args.attack_type, args.severity)

        print(f"攻击类型: {args.attack_type}")
        print(f"严重性: {args.severity}")
        print(f"匹配规则: {rule_name}")
        print(f"是否封禁: {should_block}")
        print(f"是否告警: {should_alert}")
        print(f"过期时间: {expire_hours} 小时")

    elif args.action == 'list':
        rules = rule_engine.list_rules()
        print(f"共 {len(rules)} 条规则:")
        print("-" * 80)
        for rule in rules:
            print(f"规则名称: {rule['name']}")
            print(f"描述: {rule['description']}")
            print(f"攻击类型: {', '.join(rule['attack_types'])}")
            print(f"严重性: {rule['severity']}")
            print(f"动作: {rule['action']}")
            print(f"过期时间: {rule['expire_hours']} 小时")
            print("-" * 80)