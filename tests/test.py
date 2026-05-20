#!/usr/bin/python3
# coding = utf-8

import re
from IPy import IP
import socket
import sys
data = '192.168.1.1 :  <188>Jul  3 2023 08:15:57 USG6585E_01 %%01IPS/4/TROJAN(l):A trojan horse was detected. (SyslogId=463327, VSys="public", Policy="Allow_Internet", SrcIp=10.0.0.254, DstIp=203.0.113.1, SrcPort=60684, DstPort=53, SrcZone=trust, DstZone=untrust1, User="unknown", Protocol=UDP, Application="DNS", Profile="default", SignName="Mining Pool Domain DNS Request", SignId=505470, EventNum=1, Target=server, Severity=medium, Os=all, Category=Trojan, Role=0, SrcLocation="unknown-zone", DstLocation="GuangZhou", Action=Block)'
SignName_list = re.findall(r"SignName=(.*\W+.*)", data)[0].split(',')   
SignName = SignName_list[0]

ip_Whitelist = ['10.0.0.0/8','10.0.0.88', '10.0.0.90', '10.0.0.87','192.168.0.0/16']

# ATT_SrcIp = '10.0.0.254'
# net_mask = '32'

# print(net_mask)
# if ATT_SrcIp & net_mask in ['10.0.0.0/8', '10.0.0.253', '10.0.0.88', '10.0.0.90', '10.0.0.87','192.168.0.0/16']: 
#      print("This is a DNS request.")  
#      pass      
# else:      
#     print(f'{ATT_SrcIp} 不在预定义的网段中')
ip_list = []

for x in ip_Whitelist:
    #print (x)
    try:
        for i in IP(x):
            ip_add = i.strNormal()
            ip_list.append(ip_add)
        else:
            pass        
    except ValueError as e:
        print('网段掩码错误,请确认掩码:',e)
        sys.exit(1)
#print(ip_Whitelist)
#print(ip_list)
if '192.168.1.1' in ip_list:
    print("已匹配到IP")
    pass
else:
    print('未匹配到IP')


    #print(ip_Whitelist)
#'10.0.0.254' in IP('10.0.0.0/24')
#print(SignName_list)
#print(SignName)
