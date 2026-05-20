# 华为IPS防火墙Syslog自动响应系统 - 生产部署指引

## 目录
- [系统概述](#系统概述)
- [系统要求](#系统要求)
- [部署方式选择](#部署方式选择)
- [方式一：Systemd服务部署（推荐生产环境）](#方式一systemd服务部署推荐生产环境)
- [方式二：Docker部署（推荐容器化环境）](#方式二docker部署推荐容器化环境)
- [配置说明](#配置说明)
- [防火墙配置](#防火墙配置)
- [验证部署](#验证部署)
- [运维管理](#运维管理)
- [故障排查](#故障排查)

---

## 系统概述

华为IPS防火墙Syslog自动响应系统是一个安全自动化响应平台，主要功能包括：

- **Syslog监听**：监听UDP 514端口接收华为防火墙IPS告警日志
- **自动防御**：自动将攻击源IP添加到防火墙黑名单
- **多渠道告警**：支持企业微信、邮件通知
- **Web管理界面**：提供管理仪表板（端口8081）
- **健康检查**：Prometheus指标导出（端口8080）

---

## 系统要求

### 硬件要求
| 配置项 | 最低要求 | 推荐配置 |
|--------|----------|----------|
| CPU | 2核 | 4核 |
| 内存 | 2GB | 4GB |
| 磁盘 | 20GB | 50GB SSD |
| 网络 | 100Mbps | 1Gbps |

### 软件要求
- **操作系统**：CentOS 7+ / Ubuntu 18.04+ / Debian 10+
- **Python版本**：Python 3.10+
- **Docker版本**：20.10+ （仅Docker部署方式）
- **Docker Compose版本**：2.0+ （仅Docker部署方式）

### 网络要求
- UDP 514端口开放（接收Syslog日志）
- TCP 8080端口开放（健康检查）
- TCP 8081端口开放（Web管理界面，可选）
- 能够访问华为防火墙SSH端口（默认22）
- 能够访问邮件服务器SMTP端口（默认465/587）
- 能够访问企业微信API（`qyapi.weixin.qq.com`）

---

## 部署方式选择

| 部署方式 | 适用场景 | 优点 | 缺点 |
|----------|----------|------|------|
| **Systemd服务** | 物理机/虚拟机、传统服务器 | 资源占用少、性能高、易调试 | 需要手动管理依赖 |
| **Docker** | 容器化环境、云原生应用 | 环境一致、易扩展、易维护 | 占用资源稍多 |

---

## 方式一：Systemd服务部署（推荐生产环境）

### 1. 准备工作

#### 1.1 安装系统依赖

**CentOS/RHEL:**
```bash
sudo yum install -y python3 python3-pip python3-venv git
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv git
```

#### 1.2 获取项目代码

```bash
# 克隆项目
cd /opt
sudo git clone <repository-url> python_ips_syslog
cd python_ips_syslog

# 或直接部署已有代码
cd /opt/ips-syslog
```

### 2. 配置环境

#### 2.1 创建虚拟环境

```bash
cd /opt/ips-syslog
python3 -m venv venv
source venv/bin/activate
```

#### 2.2 安装依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 2.3 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置文件
vi .env
```

**必填配置项：**

```bash
# 防火墙配置（必填）
FW_IP=你的防火墙IP地址
FW_USERNAME=防火墙SSH用户名
FW_PASSWORD=防火墙SSH密码

# 邮件配置（必填）
MAIL_HOST=smtp服务器地址
MAIL_USER=SMTP用户名
MAIL_PASSWORD=SMTP密码
MAIL_SENDER=发件人邮箱
MAIL_RECEIVERS=收件人邮箱1,收件人邮箱2

# 企业微信配置（可选）
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的webhook_key

# IP白名单（逗号分隔）
IP_WHITELIST=10.0.0.0/8,192.168.0.0/16,你的管理IP
```

### 3. 安装系统服务

#### 3.1 一键安装（推荐）

使用提供的一键部署脚本：

```bash
sudo bash scripts/deploy.sh
```

该脚本将自动完成：
- 创建必要的目录
- 安装systemd服务
- 启动服务
- 验证服务状态

#### 3.2 手动安装

```bash
# 安装服务
sudo bash scripts/install_service.sh

# 启动服务
sudo systemctl start ips-syslog

# 设置开机自启
sudo systemctl enable ips-syslog
```

### 4. 验证部署

#### 4.1 检查服务状态

```bash
sudo systemctl status ips-syslog
```

预期输出：
```
* ips-syslog.service - IPS Syslog Auto Response Service
   Loaded: loaded (/etc/systemd/system/ips-syslog.service; enabled)
   Active: active (running) since ...
```

#### 4.2 检查服务日志

```bash
# 查看实时日志
sudo journalctl -u ips-syslog -f

# 查看应用日志
tail -f logs/hw-fw-pysyslog.log
```

#### 4.3 检查端口监听

```bash
# 检查Syslog端口
sudo ss -ulnp | grep 514

# 检查健康检查端口
sudo ss -tlnp | grep 8080

# 检查Web管理界面端口
sudo ss -tlnp | grep 8081
```

#### 4.4 测试健康检查

```bash
curl http://localhost:8080/health
```

预期输出：
```json
{"status":"healthy","timestamp":"..."}
```

---

## 方式二：Docker部署（推荐容器化环境）

### 1. 准备工作

#### 1.1 安装Docker和Docker Compose

**CentOS/RHEL:**
```bash
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
```

启动Docker服务：
```bash
sudo systemctl start docker
sudo systemctl enable docker
```

### 2. 配置环境

#### 2.1 创建配置文件

```bash
cd /opt/ips-syslog
cp .env.example .env
vi .env
```

参考[Systemd服务部署](#23-配置环境变量)中的配置说明。

### 3. 启动服务

#### 3.1 使用Docker Compose（推荐）

```bash
# 构建并启动服务
sudo docker-compose up -d

# 查看服务状态
sudo docker-compose ps

# 查看日志
sudo docker-compose logs -f
```

#### 3.2 使用单独Docker命令

```bash
# 构建镜像
sudo docker build -t ips-syslog:latest .

# 运行容器
sudo docker run -d \
  --name ips-syslog \
  --restart unless-stopped \
  -p 514:514/udp \
  -p 8080:8080/tcp \
  -p 8081:8081/tcp \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.env:/app/.env:ro \
  -e TZ=Asia/Shanghai \
  --cap-add=NET_BIND_SERVICE \
  ips-syslog:latest
```

### 4. 验证部署

```bash
# 检查容器状态
sudo docker ps | grep ips-syslog

# 查看容器日志
sudo docker logs -f ips-syslog

# 测试健康检查
curl http://localhost:8080/health

# 进入容器调试
sudo docker exec -it ips-syslog bash
```

---

## 配置说明

### 防火墙配置

#### 配置华为防火墙发送Syslog

1. 登录华为防火墙Web管理界面
2. 进入「网络」→「Syslog」→「Syslog服务器」
3. 添加Syslog服务器：
   - **IP地址**：部署本系统的服务器IP
   - **端口**：514
   - **协议**：UDP
   - **日志级别**：IPS告警（Informational及以上）
4. 应用配置

#### 配置防火墙SSH访问

系统通过SSH连接防火墙执行黑名单操作，需要确保：
- 防火墙SSH服务已启用
- 使用的账号有黑名单管理权限
- 网络可达性（服务器能访问防火墙SSH端口）

### 核心配置项

| 配置项 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `FW_IP` | 防火墙IP地址 | - | 是 |
| `FW_USERNAME` | SSH用户名 | - | 是 |
| `FW_PASSWORD` | SSH密码 | - | 是 |
| `MAIL_HOST` | SMTP服务器 | smtp.163.com | 是 |
| `MAIL_USER` | SMTP用户名 | - | 是 |
| `MAIL_PASSWORD` | SMTP密码 | - | 是 |
| `MAIL_RECEIVERS` | 收件人邮箱（逗号分隔） | - | 是 |
| `WECHAT_WEBHOOK_URL` | 企业微信Webhook | - | 否 |
| `IP_WHITELIST` | 白名单IP/网段（逗号分隔） | - | 是 |
| `LOG_LEVEL` | 日志级别 | INFO | 否 |
| `SYSLOG_HOST` | Syslog监听地址 | 0.0.0.0 | 否 |
| `SYSLOG_PORT` | Syslog监听端口 | 514 | 否 |

### 日志轮转配置

系统内置日志轮转功能，配置项：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `LOG_MAX_BYTES` | 单个日志文件最大大小 | 52428800 (50MB) |
| `LOG_BACKUP_COUNT` | 保留的备份文件数量 | 10 |

---

## 验证部署

### 完整验证流程

#### 1. 服务状态检查

```bash
# Systemd部署
sudo systemctl status ips-syslog

# Docker部署
sudo docker ps | grep ips-syslog
```

#### 2. 端口监听检查

```bash
# 检查所有服务端口
sudo netstat -tlnup | grep -E '(514|8080|8081)'
```

预期输出：
```
udp  0  0 0.0.0.0:514  0.0.0.0:*  ... (syslog服务)
tcp  0  0 0.0.0.0:8080 0.0.0.0:*  ... (健康检查)
tcp  0  0 0.0.0.0:8081 0.0.0.0:*  ... (Web管理)
```

#### 3. 健康检查

```bash
curl http://localhost:8080/health
```

#### 4. 模拟Syslog测试

```bash
# 发送测试Syslog消息
echo '<14>1 2024-01-01T12:00:00.000Z testhost testapp - - - %%01IPS/4/SESS=" SrcIp=1.2.3.4 DstIp=10.0.0.1 SrcPort=12345 DstPort=80 Protocol=TCP SignName=TEST_ATTACK Severity=high"' | nc -u localhost 514

# 查看日志是否收到
tail -f logs/hw-fw-pysyslog.log
```

#### 5. Web管理界面访问

浏览器访问：`http://服务器IP:8081`

---

## 运维管理

### 服务管理命令

#### Systemd部署

```bash
# 启动服务
sudo systemctl start ips-syslog

# 停止服务
sudo systemctl stop ips-syslog

# 重启服务
sudo systemctl restart ips-syslog

# 查看状态
sudo systemctl status ips-syslog

# 查看日志
sudo journalctl -u ips-syslog -f
```

#### Docker部署

```bash
# 启动服务
sudo docker-compose start

# 停止服务
sudo docker-compose stop

# 重启服务
sudo docker-compose restart

# 查看日志
sudo docker-compose logs -f

# 重新构建并启动
sudo docker-compose up -d --build
```

### 日志管理

```bash
# 应用日志位置
ls -lh logs/

# 实时查看日志
tail -f logs/hw-fw-pysyslog.log

# 查看攻击记录
tail -f data/Att.txt
```

### 黑名单管理

```bash
# 进入虚拟环境（Systemd部署）
source /opt/ips-syslog/venv/bin/activate

# 查看当前黑名单
python -c "from blacklist_manager import blacklist_manager; print(blacklist_manager.list_all())"

# 手动添加IP到黑名单
python -c "from blacklist_manager import blacklist_manager; blacklist_manager.add_ip('1.2.3.4', expire_hours=24)"

# 手动解封IP
python -c "from blacklist_manager import blacklist_manager; blacklist_manager.remove_ip('1.2.3.4')"
```

### 白名单管理

```bash
# 查看白名单
python -c "from whitelist_manager import whitelist_manager; print(whitelist_manager.list_all())"

# 添加白名单
python -c "from whitelist_manager import whitelist_manager; whitelist_manager.add_ip('1.2.3.4')"

# 移除白名单
python -c "from whitelist_manager import whitelist_manager; whitelist_manager.remove_ip('1.2.3.4')"
```

### 配置热更新

系统支持配置文件热更新，修改`.env`文件后会自动重新加载配置，无需重启服务。

---

## 故障排查

### 常见问题

#### 1. 服务无法启动

**检查步骤：**

```bash
# 查看详细错误日志
sudo journalctl -u ips-syslog -n 100

# 检查端口占用
sudo netstat -tlnup | grep 514

# 检查配置文件
cat .env
```

**常见原因：**
- 端口514被占用（可能是系统rsyslog服务）
- 配置文件格式错误
- 虚拟环境未创建或依赖未安装

#### 2. 无法接收Syslog日志

**检查步骤：**

```bash
# 检查防火墙规则
sudo iptables -L -n | grep 514
sudo firewall-cmd --list-ports 2>/dev/null

# 检查监听状态
sudo ss -ulnp | grep 514
```

**解决方案：**

```bash
# 开放端口（firewalld）
sudo firewall-cmd --add-port=514/udp --permanent
sudo firewall-cmd --reload

# 开放端口（iptables）
sudo iptables -I INPUT -p udp --dport 514 -j ACCEPT
```

#### 3. 无法连接防火墙SSH

**检查步骤：**

```bash
# 测试SSH连接
ssh $FW_USERNAME@$FW_IP

# 测试网络连通性
ping $FW_IP
telnet $FW_IP 22
```

**常见原因：**
- 防火墙IP地址配置错误
- SSH用户名或密码错误
- 网络不通（中间有防火墙阻断）

#### 4. 邮件发送失败

**检查步骤：**

```bash
# 查看日志中的错误信息
grep "mail" logs/hw-fw-pysyslog.log | tail -20

# 测试SMTP连接
telnet $MAIL_HOST 465
telnet $MAIL_HOST 587
```

**常见原因：**
- SMTP密码错误
- SMTP服务器地址错误
- 需要开启「应用专用密码」

#### 5. 企业微信通知失败

**检查步骤：**

```bash
# 测试Webhook URL
curl -X POST "$WECHAT_WEBHOOK_URL" \
  -H 'Content-Type: application/json' \
  -d '{"msgtype":"text","text":{"content":"测试消息"}}'
```

**常见原因：**
- Webhook URL错误或已过期
- Webhook Key错误
- 企业微信机器人被禁用

### 日志分析

#### 错误日志关键字

| 关键字 | 可能原因 | 解决方案 |
|--------|----------|----------|
| `Permission denied` | 权限不足 | 检查文件/目录权限 |
| `Connection refused` | 连接被拒绝 | 检查目标服务是否运行 |
| `Timeout` | 连接超时 | 检查网络连通性 |
| `Authentication failed` | 认证失败 | 检查用户名/密码 |
| `Invalid configuration` | 配置无效 | 检查`.env`文件格式 |

### 调试模式

开启详细日志：

```bash
# 修改.env文件
echo "LOG_LEVEL=DEBUG" >> .env

# 重启服务
sudo systemctl restart ips-syslog
```

---

## 附录

### 目录结构

```
python_ips_syslog/
├── core/                   # 核心模块
│   └── syslog_to_huawei_ips.py
├── database/              # 数据库模块
├── defense/               # 防御模块
├── notification/          # 通知模块
├── scripts/               # 部署脚本
│   ├── deploy.sh         # 一键部署脚本
│   └── install_service.sh
├── logs/                  # 日志目录
├── data/                  # 数据目录
├── web_app.py            # Web管理界面
├── config.py             # 配置管理
├── .env                  # 环境变量配置
├── Dockerfile            # Docker镜像文件
├── docker-compose.yml    # Docker Compose配置
└── ips-syslog.service    # Systemd服务文件
```

### 端口说明

| 端口 | 协议 | 用途 | 外部访问 |
|------|------|------|----------|
| 514 | UDP | Syslog接收 | 是（防火墙→服务器） |
| 8080 | TCP | 健康检查 | 否（内网） |
| 8081 | TCP | Web管理界面 | 按需 |

### 支持与反馈

如有问题或建议，请通过以下方式联系：

- 项目仓库：[GitHub Repository]
- 问题反馈：[Issue Tracker]
- 文档：[Documentation]

---

**文档版本**: v1.0
**最后更新**: 2026-03-09
