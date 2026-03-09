# 部署脚本使用指南

本目录包含华为IPS防火墙Syslog自动响应系统的部署脚本。

## 脚本列表

| 脚本文件 | 说明 | 适用场景 |
|----------|------|----------|
| `deploy.sh` | 完整的一键部署脚本 | 生产环境首次部署 |
| `quick_deploy.sh` | 快速部署脚本 | 测试环境或已配置好.env的场景 |
| `uninstall.sh` | 卸载脚本 | 移除已部署的服务 |
| `install_service.sh` | Systemd服务安装脚本 | 手动安装systemd服务 |

---

## 快速开始

### 方式一：完整部署（推荐）

交互式部署脚本，支持配置向导和多种部署方式：

```bash
sudo bash scripts/deploy.sh
```

**功能特性：**
- 自动检测操作系统和环境
- 交互式配置向导
- 支持Systemd和Docker两种部署方式
- 自动安装依赖
- 部署后自动验证

### 方式二：快速部署

适用于已经配置好`.env`文件的场景：

```bash
# Systemd服务部署
sudo bash scripts/quick_deploy.sh systemd

# Docker部署
sudo bash scripts/quick_deploy.sh docker
```

**前提条件：**
- 已创建并配置`.env`文件
- 系统已安装必要的依赖（Python或Docker）

---

## 部署方式选择

### Systemd服务部署

**适用场景：** 物理机、虚拟机、传统服务器

**优点：**
- 资源占用少
- 性能高
- 易于调试
- 系统集成好

**部署命令：**
```bash
sudo bash scripts/deploy.sh
# 选择选项 1) Systemd服务部署
```

**管理命令：**
```bash
# 查看状态
sudo systemctl status ips-syslog

# 启动服务
sudo systemctl start ips-syslog

# 停止服务
sudo systemctl stop ips-syslog

# 重启服务
sudo systemctl restart ips-syslog

# 查看日志
sudo journalctl -u ips-syslog -f
```

### Docker部署

**适用场景：** 容器化环境、云原生应用

**优点：**
- 环境隔离
- 易于迁移
- 版本管理方便
- 资源限制灵活

**部署命令：**
```bash
sudo bash scripts/deploy.sh
# 选择选项 2) Docker部署
```

**管理命令：**
```bash
# 查看状态
docker ps | grep ips-syslog

# 查看日志
docker logs -f ips-syslog

# 停止容器
docker stop ips-syslog

# 启动容器
docker start ips-syslog

# 重启容器
docker restart ips-syslog

# 进入容器
docker exec -it ips-syslog bash
```

### Docker Compose部署

**适用场景：** 需要同时部署多个相关服务

**部署命令：**
```bash
sudo bash scripts/deploy.sh
# 选择选项 3) Docker Compose部署
```

**管理命令：**
```bash
# 启动服务
docker compose up -d

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f

# 停止服务
docker compose down
```

---

## 卸载服务

使用卸载脚本移除已部署的服务：

```bash
sudo bash scripts/uninstall.sh
```

**卸载选项：**
1. Systemd服务 - 仅卸载systemd服务
2. Docker容器 - 仅卸载Docker容器
3. 全部 - 卸载所有服务并可选择删除数据

---

## 配置说明

部署前需要配置`.env`文件：

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置
vi .env
```

**必填配置项：**

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `FW_IP` | 防火墙IP地址 | 192.168.1.1 |
| `FW_USERNAME` | SSH用户名 | admin |
| `FW_PASSWORD` | SSH密码 | your_password |
| `MAIL_HOST` | SMTP服务器 | smtp.example.com |
| `MAIL_USER` | SMTP用户名 | user@example.com |
| `MAIL_PASSWORD` | SMTP密码 | smtp_password |
| `MAIL_RECEIVERS` | 收件人邮箱 | admin@example.com |
| `IP_WHITELIST` | IP白名单 | 10.0.0.0/8,192.168.1.100 |

---

## 验证部署

部署完成后，可以通过以下方式验证：

```bash
# 检查服务状态
sudo systemctl status ips-syslog  # Systemd
docker ps | grep ips-syslog        # Docker

# 检查端口监听
sudo ss -tuln | grep -E '(514|8080|8081)'

# 测试健康检查
curl http://localhost:8080/health

# 访问Web管理界面
# 浏览器打开: http://服务器IP:8081
```

---

## 故障排查

### 服务无法启动

```bash
# 查看详细错误日志
sudo journalctl -u ips-syslog -n 100  # Systemd
docker logs ips-syslog                  # Docker

# 检查配置文件
cat .env

# 检查端口占用
sudo ss -tuln | grep 514
```

### 端口被占用

```bash
# 查看占用进程
sudo lsof -i :514
sudo lsof -i :8080

# 停止占用进程或修改配置端口
```

### 防火墙连接失败

```bash
# 测试SSH连接
ssh $FW_USERNAME@$FW_IP

# 测试网络连通性
ping $FW_IP
telnet $FW_IP 22
```

---

## 端口说明

| 端口 | 协议 | 用途 | 外部访问 |
|------|------|------|----------|
| 514 | UDP | Syslog接收 | 是（防火墙→服务器） |
| 8080 | TCP | 健康检查 | 否（内网） |
| 8081 | TCP | Web管理界面 | 按需 |

---

## 目录结构

部署后的目录结构：

```
python_ips_syslog/
├── core/              # 核心模块
├── database/          # 数据库模块
├── defense/           # 防御模块
├── notification/      # 通知模块
├── scripts/           # 部署脚本
├── logs/              # 日志目录（运行时创建）
│   └── hw-fw-pysyslog.log
├── data/              # 数据目录（运行时创建）
│   └── Att.txt
├── venv/              # 虚拟环境（Systemd部署时创建）
├── .env               # 环境变量配置
├── config.py          # 配置管理
└── DEPLOYMENT.md      # 完整部署文档
```

---

## 更多帮助

- 详细部署文档：查看项目根目录的 `DEPLOYMENT.md`
- 项目文档：查看项目根目录的 `README.md`
- 问题反馈：提交Issue到项目仓库
