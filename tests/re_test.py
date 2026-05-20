import re

data = 'Oct 15 2024 02:56:26+08:00 USG6585E_01 %%01IPS/4/DETECT(l)[142]:An intrusion was detected. (SyslogId=514265, VSys="public", Policy="VPN_To_Local", SrcIp=198.51.100.5, DstIp=198.51.100.1, SrcPort=36137, DstPort=53, SrcZone=untrust2, DstZone=local, User="unknown", Protocol=UDP, Application="DNS", Profile="default", SignName="ISC BIND VERSION Request", SignId=249760, EventNum=1, Target=server, Severity=low, Os=all, Category=Info-Disclosure, Reference=NA, Action=Block)'

# Extract key-value pairs
pairs = re.findall(r'(\w+)=("[^"]+"|[^,\s]+)', data)
log_info = {key: value.strip('"') for key, value in pairs}

# Print extracted information
for key, value in log_info.items():
    print(f"{key}: {value}")