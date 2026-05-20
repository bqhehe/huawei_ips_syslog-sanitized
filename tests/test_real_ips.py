#!/usr/bin/env python3
import socket

# 模拟真实格式的IPS告警日志（medium severity，应该被封禁）
ips_log_medium = '<134>Feb 28 2026 11:10:52+08:00 USG6585E %%01IPS/4/DETECT(l)[0]:An intrusion was detected. (SyslogId=582429, VSys="public", Policy="VPN_To_Local", SrcIp=198.51.100.1, DstIp=198.51.100.1, SrcPort=38284, DstPort=53, SrcZone=untrust2, DstZone=local, User="unknown", Protocol=UDP, Application="DNS", Profile="default", SignName="Directory Traversal Attempt", SignId=249760, EventNum=1, Target=server, Severity=medium, Os=all, Category=Dir-traversal, Reference=NA, Action=Block)'

# 模拟真实格式的IPS告警日志（low severity，根据规则应该只告警不封禁）
ips_log_low = '<134>Feb 28 2026 11:10:53+08:00 USG6585E %%01IPS/4/DETECT(l)[1]:An intrusion was detected. (SyslogId=582428, VSys="public", Policy="untrust_to_trust", SrcIp=198.51.100.3, DstIp=198.51.100.2, SrcPort=40135, DstPort=53, SrcZone=untrust2, DstZone=local, User="unknown", Protocol=UDP, Application="DNS", Profile="default", SignName="ISC BIND VERSION Request", SignId=249760, EventNum=1, Target=server, Severity=low, Os=all, Category=Info-Disclosure, Reference=NA, Action=Block)'

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(ips_log_medium.encode(), ('127.0.0.1', 514))
print("已发送 medium severity IPS日志")

import time
time.sleep(1)

sock.sendto(ips_log_low.encode(), ('127.0.0.1', 514))
print("已发送 low severity IPS日志")

sock.close()
