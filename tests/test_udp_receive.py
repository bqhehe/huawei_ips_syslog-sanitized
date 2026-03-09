#!/usr/bin/env python3
"""
UDP 514 端口接收测试脚本
"""
import socket
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_udp_listener():
    """监听UDP 514端口，打印所有接收到的数据"""
    try:
        # 创建UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', 514))
        sock.settimeout(10.0)  # 10秒超时

        logger.info("开始监听 UDP 514 端口...")
        logger.info("请手动触发IPS攻击或让防火墙发送测试日志...")
        logger.info("按 Ctrl+C 停止监听")

        while True:
            try:
                data, addr = sock.recvfrom(4096)
                message = data.decode('utf-8', errors='ignore')

                logger.info(f"收到来自 {addr[0]}:{addr[1]} 的数据:")
                logger.info(f"  长度: {len(data)} 字节")
                logger.info(f"  内容: {message[:200]}...")

                # 检查是否包含IPS
                if 'IPS' in message:
                    logger.info("  ✅ 这是IPS日志!")
                elif 'SECLOG' in message:
                    logger.info("  ℹ️  这是会话日志(SECLOG)")
                else:
                    logger.info("  ❓ 未知日志类型")

            except socket.timeout:
                logger.info("等待接收数据... (10秒无数据)")
            except KeyboardInterrupt:
                logger.info("用户中断，停止监听")
                break
            except Exception as e:
                logger.error(f"处理数据时出错: {e}")

    except Exception as e:
        logger.error(f"无法启动UDP监听: {e}")
        logger.error("可能需要root权限或端口已被占用")
    finally:
        if 'sock' in locals():
            sock.close()
            logger.info("UDP socket已关闭")

if __name__ == '__main__':
    test_udp_listener()