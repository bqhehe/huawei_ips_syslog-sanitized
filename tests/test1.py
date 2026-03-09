import subprocess

# 执行另一个Python文件
result = subprocess.run(['python3', '../tig/tig.py','-i','198.235.24.163'], stdout=subprocess.PIPE)

# 获取输出结果
output = result.stdout.decode('utf-8')

# 打印输出结果
print(output)
