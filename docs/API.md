# IPS Syslog 自动响应系统 - API 文档

## 目录

- [概述](#概述)
- [认证](#认证)
- [响应格式](#响应格式)
- [API 端点](#api-端点)
  - [认证相关](#认证相关)
  - [仪表板数据](#仪表板数据)
  - [黑名单管理](#黑名单管理)
  - [告警与日志](#告警与日志)
  - [系统状态](#系统状态)
  - [通知配置](#通知配置)
  - [防火墙配置](#防火墙配置)
- [错误码](#错误码)
- [示例代码](#示例代码)

---

## 概述

IPS Syslog 自动响应系统提供 RESTful API 接口，用于：

- 黑名单 IP 管理
- 告警记录查询
- 系统状态监控
- 通知配置管理
- 防火墙连接配置

**基础 URL**: `http://<server>:8081`

**Prometheus 指标 URL**: `http://<server>:8080/metrics`

**健康检查 URL**: `http://<server>:8080/health`

---

## 认证

除登录接口外，所有 API 需要会话认证。

### 认证方式

使用 Cookie 进行认证：

```http
Cookie: session_id=<your_session_id>
```

### 会话过期时间

- 默认: 3600 秒（1小时）
- 可在 `.env` 文件中配置

---

## 响应格式

### 成功响应

```json
{
  "success": true,
  "data": { ... }
}
```

### 错误响应

```json
{
  "status": "error",
  "message": "错误描述",
  "timestamp": "2026-02-28T12:00:00"
}
```

---

## API 端点

### 认证相关

#### POST /api/login

登录系统，获取会话ID。

**请求体**:
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**响应**:
```json
{
  "success": true,
  "session_id": "abc123def456"
}
```

---

#### POST /api/logout

退出登录。

**请求头**:
```http
Cookie: session_id=<session_id>
```

**响应**:
```json
{
  "success": true,
  "message": "已退出登录"
}
```

---

#### POST /api/change-password

修改当前用户密码。

**请求头**:
```http
Cookie: session_id=<session_id>
Content-Type: application/json
```

**请求体**:
```json
{
  "old_password": "admin123",
  "new_password": "newpass123",
  "confirm_password": "newpass123"
}
```

**响应**:
```json
{
  "success": true,
  "message": "密码修改成功"
}
```

---

### 仪表板数据

#### GET /api/status

获取系统状态和 Prometheus 指标。

**响应**:
```json
{
  "timestamp": "2026-02-28T12:00:00",
  "service": "ips-syslog",
  "version": "2.0.0",
  "uptime": 3600,
  "blacklist_stats": {
    "total": 100,
    "active": 85,
    "expired": 10,
    "permanent": 5
  },
  "prometheus_metrics": {
    "logs_received": 5000,
    "alerts_received": 500,
    "alerts_blocked": 450,
    "alerts_alerted": 480,
    "alerts_ignored": 20,
    "errors": 5,
    "alerts_by_severity": {
      "critical": 10,
      "high": 50,
      "medium": 200,
      "low": 240
    },
    "alerts_by_attack_type": {
      "Brute Force": 100,
      "SQL Injection": 50,
      "XSS": 30
    }
  }
}
```

---

### 黑名单管理

#### GET /api/blacklist

获取所有黑名单 IP。

**响应**:
```json
{
  "ips": [
    {
      "ip": "1.2.3.4",
      "added_at": "2026-02-28T10:00:00",
      "expire_at": "2026-02-29T10:00:00",
      "expires_in": 82800,
      "status": "active"
    }
  ]
}
```

---

#### GET /api/blacklist/stats

获取黑名单统计信息。

**响应**:
```json
{
  "total": 100,
  "active": 85,
  "expired": 10,
  "permanent": 5
}
```

---

#### POST /api/blacklist/add

添加 IP 到黑名单。

**请求头**:
```http
Cookie: session_id=<session_id>
Content-Type: application/json
```

**请求体**:
```json
{
  "ip": "1.2.3.4",
  "expire_hours": 24
}
```

**响应**:
```json
{
  "success": true
}
```

---

#### POST /api/blacklist/remove

从黑名单移除 IP。

**请求头**:
```http
Cookie: session_id=<session_id>
Content-Type: application/json
```

**请求体**:
```json
{
  "ip": "1.2.3.4"
}
```

**响应**:
```json
{
  "success": true
}
```

---

#### POST /api/blacklist/cleanup

清理过期的黑名单 IP。

**响应**:
```json
{
  "success": true,
  "count": 10
}
```

---

### 告警与日志

#### GET /api/alerts

获取最近的告警记录。

**查询参数**:
- `count`: 返回记录数量（默认: 50）

**示例请求**:
```http
GET /api/alerts?count=100
```

**响应**:
```json
[
  {
    "timestamp": "Jul  3 2023 08:39:06",
    "device": "USG6585E_01",
    "src_ip": "192.168.1.100",
    "dst_ip": "103.38.83.80",
    "src_port": "12345",
    "dst_port": "80",
    "protocol": "TCP",
    "event": "Brute Force Attack",
    "detect_time": "2026-02-28 08:39:06",
    "severity": "high"
  }
]
```

---

#### GET /api/logs

获取最近接收的 Syslog 日志（内存缓冲区）。

**查询参数**:
- `count`: 返回记录数量（默认: 100）
- `type`: 日志类型过滤（IPS/SESSION/OTHER）

**示例请求**:
```http
GET /api/logs?count=50&type=IPS
```

**响应**:
```json
[
  {
    "type": "IPS",
    "timestamp": "2026-02-28T12:00:00",
    "raw": "<134>%%01IPS/4/DETECT...",
    "parsed": {
      "SrcIp": "1.2.3.4",
      "DstIp": "192.168.1.1",
      "SignName": "Brute Force Attack",
      "Severity": "high"
    }
  }
]
```

---

#### GET /api/logs/stats

获取日志统计信息。

**响应**:
```json
{
  "total": 5000,
  "by_type": {
    "IPS": 500,
    "SESSION": 4000,
    "OTHER": 500
  }
}
```

---

#### GET /api/audit

获取审计日志。

**查询参数**:
- `count`: 返回记录数量（默认: 100）

**响应**:
```json
[
  {
    "timestamp": "2026-02-28T12:00:00",
    "event_type": "block",
    "ip": "1.2.3.4",
    "details": {
      "attack_type": "Brute Force",
      "severity": "high"
    }
  }
]
```

---

### 系统状态

#### GET /api/metrics

获取 Prometheus 格式的指标摘要。

**响应**:
```json
{
  "logs_received_total": 5000,
  "alerts_received_total": 500,
  "alerts_blocked_total": 450,
  "alerts_alerted_total": 480,
  "alerts_ignored_total": 20,
  "errors_total": 5,
  "alerts_by_severity": {
    "critical": 10,
    "high": 50,
    "medium": 200,
    "low": 240
  },
  "alerts_by_attack_type": {
    "Brute Force": 100,
    "SQL Injection": 50
  }
}
```

---

#### GET /api/rules

获取规则引擎配置。

**响应**:
```json
{
  "rules": [
    {
      "name": "critical_severity",
      "description": "严重级别攻击 - 永久封禁并告警",
      "conditions": {
        "severity": "critical"
      },
      "actions": {
        "block": true,
        "alert": true,
        "expire_hours": null
      }
    },
    {
      "name": "high_severity",
      "description": "高级别攻击 - 封禁24小时并告警",
      "conditions": {
        "severity": "high"
      },
      "actions": {
        "block": true,
        "alert": true,
        "expire_hours": 24
      }
    }
  ]
}
```

---

#### GET /api/firewall/status

检查防火墙连接状态。

**响应**:
```json
{
  "connected": true,
  "message": "防火墙连接正常"
}
```

---

### 通知配置

#### GET /api/notification/config

获取通知配置。

**响应**:
```json
{
  "enabled_channels": ["wechat", "email"],
  "wechat": {
    "enabled": true,
    "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
  },
  "dingtalk": {
    "enabled": false,
    "webhook_url": "",
    "sign_secret": ""
  },
  "feishu": {
    "enabled": false,
    "webhook_url": "",
    "sign_secret": ""
  },
  "email": {
    "enabled": true,
    "smtp_host": "smtp.163.com",
    "smtp_user": "user@163.com",
    "sender": "noreply@163.com",
    "recipients": ["admin@example.com"]
  }
}
```

---

#### POST /api/notification/update

更新通知渠道配置。

**请求头**:
```http
Cookie: session_id=<session_id>
Content-Type: application/json
```

**企业微信配置示例**:
```json
{
  "channel": "wechat",
  "enabled": true,
  "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
}
```

**钉钉配置示例**:
```json
{
  "channel": "dingtalk",
  "enabled": true,
  "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=xxx",
  "sign_secret": "SECxxx..."
}
```

**邮件配置示例**:
```json
{
  "channel": "email",
  "enabled": true,
  "smtp_host": "smtp.163.com",
  "smtp_user": "user@163.com",
  "smtp_password": "password",
  "sender": "noreply@163.com",
  "recipients": ["admin@example.com", "ops@example.com"]
}
```

---

#### POST /api/notification/test

测试通知发送。

**请求头**:
```http
Cookie: session_id=<session_id>
Content-Type: application/json
```

**请求体**:
```json
{
  "channel": "wechat"
}
```

**响应**:
```json
{
  "success": true,
  "message": "wechat 测试通知发送成功"
}
```

---

### 防火墙配置

#### POST /api/config/firewall

更新防火墙连接配置。

**请求头**:
```http
Cookie: session_id=<session_id>
Content-Type: application/json
```

**请求体**:
```json
{
  "fw_ip": "192.168.1.1",
  "fw_username": "admin",
  "fw_password": "password"
}
```

**响应**:
```json
{
  "success": true,
  "message": "防火墙配置已更新"
}
```

---

## 错误码

| HTTP 状态码 | 描述 |
|------------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 401 | 未认证或会话过期 |
| 404 | 资源不存在 |
| 405 | 方法不允许 |
| 500 | 服务器内部错误 |

---

## 示例代码

### Python 示例

```python
import requests
import json

BASE_URL = "http://localhost:8081"

# 登录
def login(username, password):
    response = requests.post(f"{BASE_URL}/api/login", json={
        "username": username,
        "password": password
    })
    return response.json()['session_id']

# 添加IP到黑名单
def add_to_blacklist(session_id, ip, expire_hours=24):
    cookies = {"session_id": session_id}
    response = requests.post(
        f"{BASE_URL}/api/blacklist/add",
        cookies=cookies,
        json={"ip": ip, "expire_hours": expire_hours}
    )
    return response.json()

# 获取系统状态
def get_status(session_id):
    cookies = {"session_id": session_id}
    response = requests.get(f"{BASE_URL}/api/status", cookies=cookies)
    return response.json()

# 使用示例
session_id = login("admin", "admin123")
result = add_to_blacklist(session_id, "1.2.3.4", 24)
print(result)
```

### curl 示例

```bash
# 登录
curl -X POST http://localhost:8081/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 获取黑名单（需要替换 SESSION_ID）
curl http://localhost:8081/api/blacklist \
  -H "Cookie: session_id=SESSION_ID"

# 添加IP到黑名单
curl -X POST http://localhost:8081/api/blacklist/add \
  -H "Cookie: session_id=SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"ip":"1.2.3.4","expire_hours":24}'
```

### JavaScript 示例

```javascript
const BASE_URL = 'http://localhost:8081';
let sessionId = '';

// 登录
async function login(username, password) {
  const response = await fetch(`${BASE_URL}/api/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  });
  const data = await response.json();
  sessionId = data.session_id;
  return data;
}

// 获取黑名单
async function getBlacklist() {
  const response = await fetch(`${BASE_URL}/api/blacklist`, {
    headers: { 'Cookie': `session_id=${sessionId}` }
  });
  return await response.json();
}

// 添加IP到黑名单
async function addToBlacklist(ip, expireHours = 24) {
  const response = await fetch(`${BASE_URL}/api/blacklist/add`, {
    method: 'POST',
    headers: {
      'Cookie': `session_id=${sessionId}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ ip, expire_hours: expireHours })
  });
  return await response.json();
}
```

---

## Prometheus 指标

系统同时提供 Prometheus 格式的指标端点：`http://<server>:8080/metrics`

可用指标：

- `ips_logs_received_total`: 接收到的日志总数
- `ips_alerts_received_total`: 接收到的告警总数
- `ips_alerts_blocked_total`: 已封禁的告警总数
- `ips_alerts_alerted_total`: 已发送通知的告警总数
- `ips_alerts_ignored_total`: 已忽略的告警总数
- `ips_errors_total`: 错误总数
- `ips_blacklist_size`: 当前黑名单IP数量
- `ips_alerts_by_severity`: 按严重性分类的告警
- `ips_alerts_by_attack_type`: 按攻击类型分类的告警

---

## 更新日志

### v2.0.0 (2026-02-28)
- 添加多渠道通知支持（企业微信、钉钉、飞书、邮件）
- 添加通知模板系统
- 添加通知重试机制
- 添加防火墙状态检查API
- 增加日志文件大小至50MB
- 添加实时日志缓冲区
