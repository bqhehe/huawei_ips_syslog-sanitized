# 华为 IPS Syslog 安全监控系统

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)

一个完整的华为防火墙 IPS（入侵防御系统）日志分析、自动响应和可视化监控平台。

## 功能特性

- **Syslog 日志接收** - 监听 UDP 514 端口，实时接收华为防火墙 IPS 告警日志
- **智能解析** - 自动解析 IPS 告警，提取攻击源 IP、目标 IP、攻击类型等关键信息
- **自动防御** - 检测到攻击后自动将恶意 IP 添加到防火墙黑名单
- **多渠道告警** - 支持邮件和企业微信（Webhook）实时告警通知
- **Web Dashboard** - 提供可视化 Web 管理界面，实时查看攻击态势
- **IP 地理定位** - 支持 MaxMind GeoIP 数据库，展示攻击来源地理位置
- **Prometheus 集成** - 导出 Prometheus 指标，支持 Grafana 可视化
- **Docker 部署** - 完整的容器化支持，一键部署

## 系统架构

```
┌─────────────────┐      UDP 514       ┌────────────────────────┐
│  华为防火墙      │ ──────────────────> │    Syslog 接收服务     │
│  (IPS 模块)     │                    │                        │
└─────────────────┘                    └───────────┬────────────┘
                                                   │
                                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                        核心处理引擎                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ 日志解析  │  │ 白名单   │  │ 告警去重  │  │ 规则引擎  │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  SSH 封禁   │      │  通知服务   │      │  数据存储   │
│  (防火墙)   │      │ (邮件/微信) │      │  (SQLite)   │
└─────────────┘      └─────────────┘      └─────────────┘
```

## 快速开始

### 方式一：一键部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/quinnli23/huawei_ips_syslog-sanitized.git
cd huawei_ips_syslog-sanitized

# 2. 配置环境变量
cp .env.example .env
vi .env  # 编辑配置文件

# 3. 一键部署
sudo bash scripts/deploy.sh
```

### 方式二：Docker 部署

```bash
# 1. 配置环境变量
cp .env.example .env
vi .env

# 2. 使用 Docker Compose 启动
docker-compose up -d

# 3. 查看日志
docker-compose logs -f
```

### 方式三：手动部署

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
vi .env

# 4. 启动服务
python core/syslog_to_huawei_ips.py
```

## 配置说明

编辑 `.env` 文件进行配置：

```bash
# 防火墙配置（必填）
FW_IP=192.168.1.1              # 防火墙 IP 地址
FW_USERNAME=admin              # SSH 用户名
FW_PASSWORD=your_password      # SSH 密码

# 邮件告警配置（必填）
MAIL_HOST=smtp.example.com     # SMTP 服务器
MAIL_USER=notification@example.com
MAIL_PASSWORD=your_smtp_password
MAIL_SENDER=notification@example.com
MAIL_RECEIVERS=admin@example.com,security@example.com

# 企业微信告警（可选）
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx

# IP 白名单（必填，逗号分隔）
IP_WHITELIST=10.0.0.0/8,192.168.0.0/16,172.16.0.0/12

# Syslog 配置
SYSLOG_HOST=0.0.0.0
SYSLOG_PORT=514

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=logs/hw-fw-pysyslog.log
```

## 端口说明

| 端口 | 协议 | 用途 |
|------|------|------|
| 514 | UDP | Syslog 日志接收 |
| 8080 | TCP | 健康检查 / Prometheus 指标 |
| 8081 | TCP | Web 管理界面 |

## 目录结构

```
huawei_ips_syslog-sanitized/
├── core/                    # 核心模块
│   └── syslog_to_huawei_ips.py    # 主程序入口
├── database/               # 数据库模块
│   ├── db.py              # 数据库连接
│   └── dao.py             # 数据访问对象
├── defense/                # 防御模块
│   ├── ips_ssh.py         # 防火墙 SSH 操作
│   └── hw_passwd.py       # 密码管理
├── notification/           # 通知模块
│   ├── notification_sender.py    # 通知发送
│   ├── notification_config.py    # 通知配置
│   └── wxrobot.py         # 企业微信机器人
├── scripts/                # 部署脚本
│   ├── deploy.sh          # 一键部署
│   ├── install_service.sh # 安装系统服务
│   └── ...
├── static/                 # 静态资源
├── tests/                  # 测试用例
├── tools/                  # 工具脚本
├── web_app.py             # Web 管理界面
├── config.py              # 配置管理
├── blacklist_manager.py   # 黑名单管理
├── whitelist_manager.py   # 白名单管理
├── rule_engine.py         # 规则引擎
├── alert_deduplicator.py  # 告警去重
├── analysis_engine.py     # 分析引擎
├── prometheus_metrics.py  # Prometheus 指标
├── ip_geo_locator.py      # IP 地理定位
├── Dockerfile             # Docker 镜像
├── docker-compose.yml     # Docker Compose 配置
└── ips-syslog.service     # Systemd 服务文件
```

## 防火墙配置

### 配置华为防火墙发送 Syslog

1. 登录华为防火墙 Web 管理界面
2. 进入 **网络** → **Syslog** → **Syslog 服务器**
3. 添加 Syslog 服务器：
   - **IP 地址**：部署本系统的服务器 IP
   - **端口**：514
   - **协议**：UDP
   - **日志级别**：IPS 告警（Informational 及以上）
4. 应用配置

## Web 管理界面

启动服务后，访问 `http://服务器IP:8081` 进入 Web 管理界面：

- **仪表盘** - 实时攻击态势概览
- **黑名单管理** - 查看/添加/删除封禁 IP
- **白名单管理** - 配置受信任的 IP
- **告警历史** - 查看历史告警记录
- **统计分析** - 攻击类型、来源地域分布

默认登录凭据：
- 用户名：`admin`
- 密码：`admin123`

> ⚠️ 请在首次登录后立即修改默认密码！

## API 接口

系统提供 RESTful API 接口：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/blacklist` | GET | 获取黑名单列表 |
| `/api/blacklist` | POST | 添加 IP 到黑名单 |
| `/api/blacklist/{ip}` | DELETE | 从黑名单移除 IP |
| `/api/whitelist` | GET | 获取白名单列表 |
| `/api/whitelist` | POST | 添加 IP 到白名单 |
| `/api/alerts` | GET | 获取告警列表 |
| `/api/stats` | GET | 获取统计数据 |
| `/health` | GET | 健康检查 |
| `/metrics` | GET | Prometheus 指标 |

## Prometheus 监控

系统内置 Prometheus 指标导出，访问 `http://服务器IP:8080/metrics` 获取指标。

主要指标：
- `ips_alerts_total` - 告警总数
- `ips_blocked_ips_total` - 封禁 IP 总数
- `ips_syslog_received_total` - 接收的 Syslog 消息数
- `ips_ssh_commands_total` - SSH 命令执行次数

## 运维命令

### Systemd 服务管理

```bash
# 查看状态
sudo systemctl status ips-syslog

# 启动/停止/重启
sudo systemctl start ips-syslog
sudo systemctl stop ips-syslog
sudo systemctl restart ips-syslog

# 查看日志
sudo journalctl -u ips-syslog -f
```

### Docker 管理

```bash
# 查看容器状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart
```

## 故障排查

### 常见问题

1. **端口 514 被占用**
   ```bash
   # 检查占用进程
   sudo lsof -i :514
   # 停止 rsyslog 服务（如果不需要）
   sudo systemctl stop rsyslog
   ```

2. **无法连接防火墙 SSH**
   ```bash
   # 测试 SSH 连接
   ssh username@firewall_ip
   # 检查网络连通性
   ping firewall_ip
   ```

3. **邮件发送失败**
   - 检查 SMTP 服务器地址和端口
   - 确认是否需要使用应用专用密码
   - 查看日志中的错误信息

## 开发与测试

```bash
# 安装开发依赖
pip install -r requirements.txt

# 运行测试
pytest tests/

# 代码格式化
black .
isort .

# 代码检查
pylint *.py
mypy .
```

## 安全建议

1. **修改默认密码** - 首次部署后立即修改 Web 界面默认密码
2. **限制访问** - 通过防火墙限制 Web 管理界面的访问来源
3. **定期备份** - 定期备份 `data/` 目录和配置文件
4. **监控日志** - 定期检查日志，及时发现异常
5. **更新依赖** - 定期更新 Python 依赖包

## 许可证

[MIT License](LICENSE)

## 贡献

欢迎提交 Issue 和 Pull Request！

## 相关文档

- [快速启动指南](QUICKSTART.md)
- [详细部署文档](DEPLOYMENT.md)
- [使用说明](USAGE.md)
- [API 文档](docs/API.md)
