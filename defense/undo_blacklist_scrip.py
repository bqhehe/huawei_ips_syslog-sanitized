#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
从防火墙黑名单中移除IP的脚本
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from defense.ips_ssh import undo_blacklist, send_email


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python3 undo_blacklist_scrip.py <IP地址>")
        sys.exit(1)

    ip = sys.argv[1]

    # 从黑名单中移除IP
    if undo_blacklist(ip):
        print(f"成功从黑名单中移除 {ip}")

        # 发送邮件通知
        subject = f"黑名单解除绑定通知: {ip}"
        content = f"解除黑名单IP: {ip}"
        send_email(subject, content)
    else:
        print(f"从黑名单中移除 {ip} 失败")
        sys.exit(1)


if __name__ == "__main__":
    main()