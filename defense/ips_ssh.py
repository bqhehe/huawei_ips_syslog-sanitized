#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
华为防火墙SSH操作模块
提供通过SSH连接华为防火墙，执行黑名单操作的功能
"""

import sys
import os
import time
import logging
import paramiko
import smtplib
from email.mime.text import MIMEText
from email.header import Header

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from audit_logger import audit_logger

logger = logging.getLogger(__name__)


class FirewallSSH:
    """防火墙SSH连接类"""

    def __init__(self):
        self.host = Config.FW_IP
        self.port = 22
        self.username = Config.FW_USERNAME
        self.password = Config.FW_PASSWORD
        self.ssh = None
        self.shell = None

    def connect(self, timeout: int = 30) -> bool:
        """
        连接到防火墙
        """
        try:
            self.ssh = paramiko.SSHClient()

            # 自动添加主机密钥策略（用于自动化场景）
            # 在生产环境中，应该使用已知主机密钥文件
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # 尝试连接
            self.ssh.connect(
                self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=timeout,
                allow_agent=False,
                look_for_keys=False
            )

            # 创建交互式shell
            self.shell = self.ssh.invoke_shell()
            time.sleep(1)

            logger.info(f"成功连接到防火墙 {self.host}")
            return True

        except paramiko.AuthenticationException:
            logger.error(f"防火墙 {self.host} 认证失败")
            return False
        except paramiko.SSHException as e:
            logger.error(f"SSH连接错误: {e}")
            return False
        except Exception as e:
            logger.error(f"连接防火墙时发生错误: {e}")
            return False

    def execute_command(self, command: str, wait_time: float = 0.5) -> str:
        """
        执行命令并返回输出
        """
        if not self.shell:
            logger.error("SSH连接未建立")
            return ""

        try:
            self.shell.send(command + '\n')
            time.sleep(wait_time)

            # 使用非阻塞方式接收数据，设置超时
            output = ""
            self.shell.setblocking(0)  # 设置为非阻塞模式

            try:
                import socket
                # 尝试多次读取，直到没有数据或超时
                for _ in range(10):  # 最多尝试10次
                    try:
                        chunk = self.shell.recv(65535).decode('utf-8')
                        output += chunk
                        if not chunk:
                            break
                    except socket.error:
                        # 没有数据可读
                        break
                    time.sleep(0.05)
            except Exception as e:
                logger.debug(f"接收数据时出现异常: {e}")

            # 恢复阻塞模式
            self.shell.setblocking(1)

            return output
        except Exception as e:
            logger.error(f"执行命令时发生错误: {e}")
            return ""

    def add_to_blacklist(self, ip: str, timeout_minutes: int = None) -> bool:
        """
        将IP添加到黑名单

        Args:
            ip: IP地址
            timeout_minutes: 过期时间（分钟），None表示永不过期
        """
        try:
            # 验证IP格式
            import ipaddress
            ipaddress.ip_address(ip)

            # 构建命令
            if timeout_minutes:
                cmd = f'firewall blacklist item source-ip {ip} timeout {timeout_minutes}'
            else:
                cmd = f'firewall blacklist item source-ip {ip}'

            # 执行命令
            self.execute_command('screen-length 0 temporary')
            time.sleep(0.3)
            self.execute_command('sys')
            time.sleep(0.3)
            self.execute_command(cmd)
            time.sleep(0.5)
            self.execute_command('quit')
            time.sleep(0.3)
            self.execute_command('save')
            time.sleep(0.3)
            self.execute_command('Y')
            time.sleep(1)

            logger.info(f"成功将IP {ip} 添加到黑名单，过期时间: {timeout_minutes or '永不过期'} 分钟")
            return True

        except ValueError:
            logger.error(f"无效的IP地址: {ip}")
            return False
        except Exception as e:
            logger.error(f"添加IP到黑名单时发生错误: {e}")
            return False

    def remove_from_blacklist(self, ip: str) -> bool:
        """
        从黑名单中移除IP
        """
        try:
            # 验证IP格式
            import ipaddress
            ipaddress.ip_address(ip)

            # 执行命令
            self.execute_command('screen-length 0 temporary')
            time.sleep(0.3)
            self.execute_command('sys')
            time.sleep(0.3)

            # 移除黑名单（增加等待时间确保命令执行完成）
            self.execute_command(f'undo firewall blacklist item source-ip {ip}', wait_time=1)
            time.sleep(0.5)

            # 退出系统视图
            self.execute_command('quit')
            time.sleep(0.3)

            # 保存配置（华为防火墙有些版本需要确认）
            self.execute_command('save', wait_time=0.5)
            time.sleep(0.8)
            # 发送确认 Y
            self.execute_command('Y', wait_time=1)
            time.sleep(0.5)

            logger.info(f"成功从黑名单中移除IP {ip}")
            return True

        except ValueError:
            logger.error(f"无效的IP地址: {ip}")
            return False
        except Exception as e:
            logger.error(f"从黑名单移除IP时发生错误: {e}")
            return False

    def close(self):
        """
        关闭SSH连接
        """
        if self.ssh:
            self.ssh.close()
            logger.info("SSH连接已关闭")


def ips_ssh(ip: str, expire_hours: int = None) -> bool:
    """
    将IP添加到防火墙黑名单

    Args:
        ip: IP地址
        expire_hours: 过期时间（小时），None表示永不过期
    """
    max_attempts = 3
    delay = 1.0
    backoff = 2.0

    # 将小时转换为分钟
    timeout_minutes = expire_hours * 60 if expire_hours else None

    for attempt in range(max_attempts):
        firewall = FirewallSSH()
        try:
            if firewall.connect():
                success = firewall.add_to_blacklist(ip, timeout_minutes)
                if success:
                    return True
                else:
                    logger.warning(f"添加IP到黑名单失败，尝试 {attempt + 1}/{max_attempts}")
        except Exception as e:
            logger.warning(f"SSH连接失败，尝试 {attempt + 1}/{max_attempts}: {e}")
        finally:
            firewall.close()

        # 如果不是最后一次尝试，等待后重试
        if attempt < max_attempts - 1:
            time.sleep(delay)
            delay *= backoff

    logger.error(f"添加IP {ip} 到黑名单失败，已重试 {max_attempts} 次")
    return False


def undo_blacklist(ip: str) -> bool:
        """
        从防火墙黑名单中移除IP
        """
        firewall = FirewallSSH()
        try:
            if firewall.connect():
                success = firewall.remove_from_blacklist(ip)
                if success:
                    audit_logger.log_unblock(ip, 'manual')
                return success
            return False
        finally:
            firewall.close()

def send_email(subject: str, content: str, recipients: list = None) -> bool:
    """
    发送邮件通知（带重试机制）
    """
    max_attempts = 3
    delay = 1.0
    backoff = 2.0

    if recipients is None:
        recipients = Config.MAIL_RECEIVERS

    message = MIMEText(content, 'plain', 'utf-8')
    message['From'] = Header("防火墙威胁防护告警", 'utf-8')
    message['To'] = Header(recipients[0], 'utf-8')
    message['Subject'] = Header(subject, 'utf-8')

    for attempt in range(max_attempts):
        try:
            with smtplib.SMTP(Config.MAIL_HOST, 25, timeout=30) as smtp_obj:
                smtp_obj.login(Config.MAIL_USER, Config.MAIL_PASSWORD)
                smtp_obj.sendmail(Config.MAIL_SENDER, recipients, message.as_string())

            logger.info(f"邮件发送成功: {subject}")
            return True

        except smtplib.SMTPException as e:
            logger.warning(f"邮件发送失败，尝试 {attempt + 1}/{max_attempts}: {e}")
        except Exception as e:
            logger.warning(f"发送邮件时发生错误，尝试 {attempt + 1}/{max_attempts}: {e}")

        # 如果不是最后一次尝试，等待后重试
        if attempt < max_attempts - 1:
            time.sleep(delay)
            delay *= backoff

    logger.error(f"邮件发送失败，已重试 {max_attempts} 次: {subject}")
    return False


if __name__ == "__main__":
    # 测试代码
    import argparse

    parser = argparse.ArgumentParser(description='华为防火墙黑名单管理工具')
    parser.add_argument('action', choices=['add', 'remove', 'test-email'], help='操作类型')
    parser.add_argument('--ip', help='IP地址')
    args = parser.parse_args()

    if args.action == 'add' and args.ip:
        if ips_ssh(args.ip):
            print(f"成功将 {args.ip} 添加到黑名单")
        else:
            print(f"添加 {args.ip} 到黑名单失败")

    elif args.action == 'remove' and args.ip:
        if undo_blacklist(args.ip):
            print(f"成功从黑名单中移除 {args.ip}")
        else:
            print(f"从黑名单中移除 {args.ip} 失败")

    elif args.action == 'test-email':
        if send_email("测试邮件", "这是一封测试邮件"):
            print("测试邮件发送成功")
        else:
            print("测试邮件发送失败")