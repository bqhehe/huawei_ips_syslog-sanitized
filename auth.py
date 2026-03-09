#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Web认证模块
提供用户认证和会话管理
"""

import hashlib
import secrets
import json
import time
from typing import Dict, Optional
from pathlib import Path

# 会话存储（生产环境应使用Redis等）
sessions: Dict[str, dict] = {}
SESSION_TIMEOUT = 3600  # 1小时

# 用户存储
USERS_FILE = "data/users.json"


def hash_password(password: str) -> str:
    """哈希密码"""
    return hashlib.sha256(password.encode()).hexdigest()


def init_users():
    """初始化用户数据"""
    users_file = Path(USERS_FILE)
    if not users_file.exists():
        # 创建默认管理员用户
        default_users = {
            "admin": {
                "password": hash_password("admin123"),
                "role": "admin"
            }
        }
        users_file.parent.mkdir(parents=True, exist_ok=True)
        with open(users_file, 'w') as f:
            json.dump(default_users, f, indent=2)
        print("已创建默认用户: admin / admin123")


def load_users() -> dict:
    """加载用户数据"""
    users_file = Path(USERS_FILE)
    if not users_file.exists():
        init_users()
    with open(users_file, 'r') as f:
        return json.load(f)


def verify_user(username: str, password: str) -> bool:
    """验证用户"""
    users = load_users()
    if username in users:
        return users[username]["password"] == hash_password(password)
    return False


def create_session(username: str) -> str:
    """创建会话"""
    session_id = secrets.token_hex(32)
    sessions[session_id] = {
        "username": username,
        "created_at": time.time()
    }
    return session_id


def verify_session(session_id: str) -> Optional[dict]:
    """验证会话"""
    if session_id in sessions:
        session = sessions[session_id]
        if time.time() - session["created_at"] < SESSION_TIMEOUT:
            return session
        else:
            # 会话过期，删除
            del sessions[session_id]
    return None


def destroy_session(session_id: str):
    """销毁会话"""
    if session_id in sessions:
        del sessions[session_id]


def cleanup_expired_sessions():
    """清理过期会话"""
    current_time = time.time()
    expired = [
        sid for sid, session in sessions.items()
        if current_time - session["created_at"] >= SESSION_TIMEOUT
    ]
    for sid in expired:
        del sessions[sid]


def change_password(username: str, old_password: str, new_password: str) -> bool:
    """修改密码"""
    users = load_users()
    if username not in users:
        return False

    if users[username]["password"] != hash_password(old_password):
        return False

    users[username]["password"] = hash_password(new_password)

    users_file = Path(USERS_FILE)
    with open(users_file, 'w') as f:
        json.dump(users, f, indent=2)

    return True


# 初始化用户
init_users()