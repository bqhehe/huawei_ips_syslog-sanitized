import sys
import nmap
from pprint import pprint


def nmap_A_scan(scrip):
	nm = nmap.PortScanner()
	scan_raw_result = nm.scan(hosts=scrip, arguments='-v -n -A')
	#pprint(scan_raw_result)
	# print('#'*25 + '扫描信息' + '#'*25)
	# pprint(scan_raw_result['scan'])
	# print('#'*25 + '扫描信息' + '#'*25)

#	print(len(scan_raw_result))
#	print(len(scan_raw_result['scan']))
	for host in scan_raw_result['scan']:
		if scan_raw_result['scan'][host]['status']['state'] == 'up':
			print('#'*17 + ' Host: ' + host + '#'*17)
			#print('Host: %s' % host)
#			print('='*20 + '开放端口清单' + '='*20)
			#print(scan_raw_result['scan'][host]['portused'])
#			for port in scan_raw_result['scan'][host]['portused']:
#				if port['state'] == 'open':
#					print('开放端口号: ' + port['proto'] + '/' + port['portid'])
			print('-'*20 + ' 操作系统猜测 ' + '-'*20)
			#print(scan_raw_result['scan'][host]['osmatch'])
			for os in scan_raw_result['scan'][host]['osmatch']:
				pprint('操作系统为: ' + os['name'] + '   准确度为: ' + os['accuracy'])
			print('-'*20 + ' 系统nbstat信息 ' + '-'*20)
			#print('='*50 + 'vendor' + '='*50)
			#print(scan_raw_result['scan'][host]['vendor'])
			#print('='*50 + 'uptime' + '='*50)
			#print(scan_raw_result['scan'][host]['uptime'])
			for nbstat in scan_raw_result['scan'][host]['hostscript']:
				if nbstat['id'] == 'nbstat':
					pprint('系统信息: ' + nbstat['output'])
			idno = 1
			try:
				for port in scan_raw_result['scan'][host]['tcp']:
					try:
						print('-'*17 + 'TCP服务详细信息' + '[' + str(idno) + ']' + '-'*17)
						idno = idno + 1
						print('TCP端口号:' + str(port))
						try:
							print('状态: ' + scan_raw_result['scan'][host]['tcp'][port]['state'])
						except:
							pass
						try:
							print('原因: ' + scan_raw_result['scan'][host]['tcp'][port]['reason'])
						except:
							pass
						try:
							print('额外信息: ' + scan_raw_result['scan'][host]['tcp'][port]['extrainfo'])
						except:
							pass
						try:
							print('名字: ' + scan_raw_result['scan'][host]['tcp'][port]['name'])
						except:
							pass
						try:
							print('版本: ' + scan_raw_result['scan'][host]['tcp'][port]['version'])
						except:
							pass
						try:
							print('产品: ' + scan_raw_result['scan'][host]['tcp'][port]['product'])
						except:
							pass
						try:
							print('CPE: ' + scan_raw_result['scan'][host]['tcp'][port]['cpe'])
						except:
							pass
						try:
							print('脚本: ' + scan_raw_result['scan'][host]['tcp'][port]['script'])	
						except:
							pass
					except:
						pass
			except:
				pass

			idno = 1
			try:
				for port in scan_raw_result['scan'][host]['udp']:
					try:
						print('-'*17 + 'UDP服务详细信息' + '[' + str(idno) + ']' + '-'*17)
						idno = idno + 1
						print('UDP端口号:' + str(port))
						try:
							print('状态: ' + scan_raw_result['scan'][host]['udp'][port]['state'])
						except:
							pass
						try:
							print('原因: ' + scan_raw_result['scan'][host]['udp'][port]['reason'])
						except:
							pass
						try:
							print('额外信息: ' + scan_raw_result['scan'][host]['udp'][port]['extrainfo'])
						except:
							pass
						try:
							print('名字: ' + scan_raw_result['scan'][host]['udp'][port]['name'])
						except:
							pass
						try:
							print('版本: ' + scan_raw_result['scan'][host]['udp'][port]['version'])
						except:
							pass
						try:
							print('产品: ' + scan_raw_result['scan'][host]['udp'][port]['product'])
						except:
							pass
						try:
							print('CPE: ' + scan_raw_result['scan'][host]['udp'][port]['cpe'])
						except:
							pass
						try:
							print('脚本: ' + scan_raw_result['scan'][host]['udp'][port]['script'])	
						except:
							pass
					except:
						pass
			except:
				pass
			#print('='*50 + 'hostnames' + '='*50)
			#print(scan_raw_result['scan'][host]['hostnames'])
			print('-'*20 + '地址详细信息' + '-'*20)
			try:
				print('IP地址: ' + scan_raw_result['scan'][host]['addresses']['ipv4'])
				print('MAC地址: ' + scan_raw_result['scan'][host]['addresses']['mac'])
			except:
				pass

#	for IP in scan_raw_result['scan']:
#		if scan_raw_result['scan'][IP]['status']['state'] == 'up':
#			print( '%-20s %5s' % (scan_raw_result['scan'][IP]['addresses']['ipv4'],'is UP'))

if __name__ == '__main__':
	nmap_A_scan(sys.argv[1])