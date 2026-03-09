#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
企业微信机器人通知模块
通过企业微信webhook发送告警消息
"""

import sys
import os
import logging
import requests
import json
import time

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config

logger = logging.getLogger(__name__)


def send_wechat_message(text: str, mentioned_mobile_list: list = None) -> bool:
    """
    发送企业微信消息（带重试机制）

    Args:
        text: 消息内容
        mentioned_mobile_list: 需要@的手机号列表

    Returns:
        bool: 发送是否成功
    """
    max_attempts = 3
    delay = 1.0
    backoff = 2.0

    headers = {'Content-Type': 'application/json;charset=utf-8'}

    # 构建消息体
    message_data = {
        "msgtype": "text",
        "text": {
            "content": text
        }
    }

    # 添加@成员
    if mentioned_mobile_list:
        message_data["text"]["mentioned_mobile_list"] = mentioned_mobile_list

    for attempt in range(max_attempts):
        try:
            # 发送请求
            response = requests.post(
                Config.WECHAT_WEBHOOK_URL,
                json.dumps(message_data),
                headers=headers,
                timeout=10
            )

            # 检查响应
            result = response.json()
            if result.get('errcode') == 0:
                logger.info("企业微信消息发送成功")
                return True
            else:
                logger.warning(f"企业微信消息发送失败，尝试 {attempt + 1}/{max_attempts}: {result}")

        except requests.exceptions.Timeout:
            logger.warning(f"企业微信消息发送超时，尝试 {attempt + 1}/{max_attempts}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"企业微信消息发送请求错误，尝试 {attempt + 1}/{max_attempts}: {e}")
        except Exception as e:
            logger.warning(f"发送企业微信消息时发生错误，尝试 {attempt + 1}/{max_attempts}: {e}")

        # 如果不是最后一次尝试，等待后重试
        if attempt < max_attempts - 1:
            time.sleep(delay)
            delay *= backoff

    logger.error(f"企业微信消息发送失败，已重试 {max_attempts} 次")
    return False


def msg(text: str):
    """
    发送消息（兼容旧接口）
    """
    send_wechat_message(text)


if __name__ == '__main__':
    # 测试代码
    import argparse

    parser = argparse.ArgumentParser(description='企业微信机器人测试工具')
    parser.add_argument('message', help='要发送的消息内容')
    parser.add_argument('--at', nargs='+', help='需要@的手机号列表')
    args = parser.parse_args()

    if send_wechat_message(args.message, args.at):
        print("消息发送成功")
    else:
        print("消息发送失败")
        sys.exit(1)