# 华为IPS防火墙Syslog自动响应系统 - 使用指南

## 目录
- [系统概述](#系统概述)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [服务管理](#服务管理)
- [功能说明](#功能说明)
- [常用命令](#常用命令)
- [故障排查](#故障排查)

---

## 系统概述

本系统是一个自动化的IPS（入侵防御系统）告警响应系统，主要功能包括：

- **Syslog监控**: 监听UDP 514端口接收华为防火墙的IPS告警日志
- **自动防御**: 自动将攻击源IP添加到防火墙黑名单
- **告警通知**: 通过企业微信和邮件发送告警通知
- **自动解封**: 支持设置IP黑名单过期时间，自动清理过期IP
- **速率限制**: 防止伪造Syslog导致大量请求
- **异步处理**: 异步执行防御操作，不阻塞主流程

---

## 快速开始

### 1. 环境要求

- Python 3.10+
- Linux系统（推荐Ubuntu 20.04+）
- 网络访问权限（用于发送通知）

### 2. 安装依赖

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置系统

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置文件
vim .env
```

**必须配置的项**:
```bash
# 防火墙密码
FW_PASSWORD=your_firewall_password_here

# 邮件密码
MAIL_PASSWORD=your_mail_password_here

# 企业微信webhook密钥
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your_webhook_key_here
```

### 4. 启动服务

#### 方式一：直接启动
```bash
bash scripts/reboot.sh
```

#### 方式二：systemd服务（推荐）
```bash
# 安装服务
sudo bash scripts/install_service.sh

# 启动服务
sudo systemctl start ips-syslog

# 查看状态
sudo systemctl status ips-syslog
```

#### 方式三：Docker部署
```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

---

## 配置说明

### 配置文件 (.env)

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| FW_IP | 防火墙IP地址 | 192.168.1.1 |
| FW_USERNAME | 防火墙用户名 | admin |
| FW_PASSWORD | 防火墙密码 | (必须配置) |
| MAIL_HOST | 邮件服务器 | smtp.163.com |
| MAIL_USER | 邮件用户名 | monitor_user |
| MAIL_PASSWORD | 邮件密码 | (必须配置) |
| MAIL_SENDER | 发件人地址 | monitor@example.com |
| MAIL_RECEIVERS | 收件人列表 | admin@example.com |
| WECHAT_WEBHOOK_URL | 企业微信webhook | (必须配置) |
| IP_WHITELIST | IP白名单 | (见配置文件) |
| LOG_LEVEL | 日志级别 | INFO |
| LOG_FILE | 日志文件路径 | logs/hw-fw-pysyslog.log |
| LOG_MAX_BYTES | 日志文件最大大小 | 10485760 (10MB) |
| LOG_BACKUP_COUNT | 日志备份数量 | 5 |
| ATTACK_FILE | 攻击记录文件 | data/Att.txt |
| SYSLOG_HOST | Syslog监听地址 | 0.0.0.0 |
| SYSLOG_PORT | Syslog监听端口 | 514 |

### IP白名单配置

IP白名单支持单个IP和网段，使用逗号分隔：

```bash
# 单个IP
IP_WHITELIST=192.168.1.1,10.0.0.1

# 网段
IP_WHITELIST=192.168.1.0/24,10.0.0.0/8

# 混合
IP_WHITELIST=192.168.1.1,10.0.0.0/24,172.16.0.0/16
```

---

## 服务管理

### 统一管理脚本 (推荐)

项目提供 `scripts/service.sh` 统一管理脚本，支持所有服务操作：

```bash
# 启动服务
sudo bash scripts/service.sh start

# 停止服务
sudo bash scripts/service.sh stop

# 重启服务
sudo bash scripts/service.sh restart

# 查看状态
bash scripts/service.sh status

# 查看实时日志
bash scripts/service.sh logs

# 开机自启动
sudo bash scripts/service.sh enable    # 启用
sudo bash scripts/service.sh disable   # 禁用

# 查看帮助
bash scripts/service.sh help
```

### 开机自启动设置

```bash
# 首次安装 - 安装并启用systemd服务
sudo bash scripts/service.sh install
sudo bash scripts/service.sh enable

# 启动服务
sudo bash scripts/service.sh start
```

### Docker部署

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f
```

---

## 功能说明

### 1. 自动防御流程

```
防火墙Syslog → UDP 514端口 → 日志解析 → 白名单检查
    ↓
不在白名单 → 添加到黑名单 → 发送告警通知 → 记录日志
```

### 2. 速率限制

- 默认限制：每个IP每60秒最多100次请求
- 超过限制的请求将被跳过并记录警告日志

### 3. 自动解封

- 默认过期时间：24小时
- 自动清理：每小时检查一次并清理过期IP
- 手动清理：`bash scripts/auto_unblock.sh`

### 4. 黑名单管理

```bash
# 查看黑名单
python3 blacklist_manager.py list

# 查看统计
python3 blacklist_manager.py stats

# 手动添加IP
python3 blacklist_manager.py add --ip 192.168.1.1 --expire 24

# 手动移除IP
python3 blacklist_manager.py remove --ip 192.168.1.1

# 清理过期IP
python3 blacklist_manager.py cleanup
```

### 5. 防火墙操作

```bash
# 添加IP到黑名单
python3 defense/ips_ssh.py add --ip 192.168.1.1

# 从黑名单移除IP
python3 defense/ips_ssh.py remove --ip 192.168.1.1

# 测试邮件发送
python3 defense/ips_ssh.py test-email
```

### 6. 企业微信通知

```bash
# 发送测试消息
python3 notification/wxrobot.py "测试消息"

# 发送消息并@成员
python3 notification/wxrobot.py "测试消息" --at 13800000000 13800000001
```

---

## 常用命令

### 系统管理

```bash
# 安装systemd服务
sudo bash scripts/install_service.sh

# 卸载systemd服务
sudo bash scripts/uninstall_service.sh

# 自动解封
bash scripts/auto_unblock.sh
```

### 测试

```bash
# 运行单元测试
bash tests/run_tests.sh

# 或使用pytest
pytest tests/ -v
```

### Docker

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart
```

---

## 故障排查

### 1. 服务无法启动

**检查配置文件**:
```bash
# 确认.env文件存在
ls -la .env

# 检查配置是否正确
cat .env
```

**检查端口占用**:
```bash
# 检查514端口是否被占用
sudo netstat -tuln | grep 514

# 或使用ss命令
sudo ss -tuln | grep 514
```

**检查日志**:
```bash
tail -f logs/service.log
```

### 2. 无法连接防火墙

**检查网络连接**:
```bash
# 测试防火墙连通性
ping 192.168.1.1

# 测试SSH端口
telnet 192.168.1.1 22
```

**检查防火墙配置**:
```bash
# 确认IP、用户名、密码正确
cat .env | grep FW_
```

### 3. 告警通知失败

**企业微信通知失败**:
- 检查webhook URL是否正确
- 确认webhook密钥有效
- 检查网络连接

**邮件通知失败**:
- 检查SMTP配置是否正确
- 确认邮箱密码（可能需要授权码）
- 检查网络连接和防火墙设置

### 4. IP未被封禁

**检查白名单**:
```bash
# 确认IP不在白名单中
cat .env | grep IP_WHITELIST
```

**检查黑名单状态**:
```bash
python3 blacklist_manager.py list
```

**查看日志**:
```bash
tail -f logs/hw-fw-pysyslog.log
```

### 5. 日志文件过大

系统已配置日志轮转（最大10MB，保留5个备份），如需调整：

编辑 `.env` 文件：
```bash
LOG_MAX_BYTES=20971520  # 20MB
LOG_BACKUP_COUNT=10     # 保留10个备份
```

重启服务生效。

---

## 安全建议

1. **密码管理**:
   - 不要将 `.env` 文件提交到版本控制系统
   - 定期更换密码
   - 使用强密码

2. **网络安全**:
   - 限制Syslog端口的访问来源
   - 使用防火墙规则保护服务端口
   - 定期更新系统和依赖包

3. **日志审计**:
   - 定期检查日志文件
   - 关注异常告警
   - 定期清理旧日志

4. **权限控制**:
   - 使用非root用户运行服务（如使用systemd服务）
   - 限制日志和数据目录的访问权限

---

## 技术支持

如遇问题，请按以下步骤排查：

1. 查看日志文件
2. 检查配置文件
3. 运行单元测试
4. 查看系统资源使用情况

---

## 版本信息

- Python版本: 3.10+
- 系统版本: 2.0.0
- 最后更新: 2026-01-21