#!/usr/bin/env python3
import socket

# 模拟一条IPS告警日志
ips_log = '<134>2026-02-28 11:30:00 USG6585E %%01IPS/4/IPS(a):[skb] SrcIp=192.168.1.100 DstIp=192.168.1.1 SrcPort=12345 DstPort=80 Protocol=TCP Attack="Brute Force Attack" Severity=high Action=drop DetectTime=2026-02-28 11:30:00 SignName=SSH_Brute_Force'

# 发送到本地514端口
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(ips_log.encode(), ('127.0.0.1', 514))
sock.close()

print("已发送模拟IPS告警日志到127.0.0.1:514")
print(f"日志内容: {ips_log}")
