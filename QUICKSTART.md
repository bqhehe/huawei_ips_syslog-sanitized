# 快速启动指南

## 1. 解压项目

```bash
tar -xzf python_ips_syslog-YYYYMMDD_HHMMSS-sanitized.tar.gz -C /opt/python-code/
cd /opt/python-code/python_ips_syslog
```

## 2. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置
vi .env
```

**必填配置项：**
- `FW_IP` - 防火墙IP地址
- `FW_USERNAME` - SSH用户名
- `FW_PASSWORD` - SSH密码
- `MAIL_HOST` - SMTP服务器
- `MAIL_USER` - SMTP用户名
- `MAIL_PASSWORD` - SMTP密码
- `MAIL_RECEIVERS` - 收件人邮箱（逗号分隔）
- `IP_WHITELIST` - 白名单IP/网段（逗号分隔）

## 3. 一键部署

```bash
sudo bash scripts/deploy.sh
```

按照提示选择部署方式：
1. Systemd服务部署（推荐生产环境）
2. Docker部署
3. Docker Compose部署

## 4. 验证部署

```bash
# 检查服务状态
sudo systemctl status ips-syslog  # Systemd部署
docker ps | grep ips-syslog        # Docker部署

# 测试健康检查
curl http://localhost:8080/health

# 访问Web管理界面
# 浏览器打开: http://服务器IP:8081
```

## 端口说明

| 端口 | 协议 | 用途 |
|------|------|------|
| 514 | UDP | Syslog接收 |
| 8080 | TCP | 健康检查 |
| 8081 | TCP | Web管理界面 |

## 需要帮助？

查看完整部署文档：`DEPLOYMENT.md`
