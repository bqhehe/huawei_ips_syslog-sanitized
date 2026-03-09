#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GeoLite2数据库下载脚本
自动下载并更新 MaxMind GeoLite2 城市数据库

使用方法:
    python3 scripts/download_geoip_db.py              # 下载到默认位置
    python3 scripts/download_geoip_db.py --force      # 强制重新下载
    python3 scripts/download_geoip_db.py --check      # 仅检查数据库是否需要更新

注意: 需要注册 MaxMind 账号获取免费的 License Key
注册地址: https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
"""

import os
import sys
import argparse
import logging
import hashlib
import tarfile
import gzip
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# 添加父目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# GeoLite2 数据库下载配置
GEOLITE_URL = "https://download.maxmind.com/app/geoip_download"
GEOLITE_EDITION_ID = "GeoLite2-City"
GEOLITE_SUFFIX = "tar.gz"

# 数据库存储位置
DEFAULT_DB_DIR = os.path.join(BASE_DIR, 'data')
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, 'GeoLite2-City.mmdb')

# 数据库更新周期（默认每周更新一次）
UPDATE_INTERVAL_DAYS = 7


class GeoIPDownloader:
    """GeoLite2数据库下载器"""

    def __init__(self, license_key: str = None, account_id: str = None):
        """
        初始化下载器

        Args:
            license_key: MaxMind License Key
            account_id: MaxMind Account ID (可选，新版本只需要license_key)
        """
        self.license_key = license_key or os.getenv('MAXMIND_LICENSE_KEY')
        self.account_id = account_id or os.getenv('MAXMIND_ACCOUNT_ID')
        self.db_dir = DEFAULT_DB_DIR
        self.db_path = DEFAULT_DB_PATH

        if not self.license_key:
            logger.warning("未设置 MAXMIND_LICENSE_KEY，将尝试从配置文件读取")

    def check_db_exists(self) -> bool:
        """检查数据库是否存在"""
        return os.path.exists(self.db_path)

    def check_db_age(self) -> int:
        """
        检查数据库年龄（天数）

        Returns:
            数据库文件的天数，如果文件不存在返回999
        """
        if not self.check_db_exists():
            return 999

        mtime = os.path.getmtime(self.db_path)
        file_date = datetime.fromtimestamp(mtime)
        age = (datetime.now() - file_date).days
        return age

    def check_db_need_update(self, force: bool = False) -> bool:
        """
        检查数据库是否需要更新

        Args:
            force: 是否强制更新

        Returns:
            是否需要更新
        """
        if force:
            return True

        if not self.check_db_exists():
            return True

        age = self.check_db_age()
        if age >= UPDATE_INTERVAL_DAYS:
            logger.info(f"数据库已使用 {age} 天，需要更新")
            return True

        logger.info(f"数据库当前 {age} 天，无需更新（更新周期: {UPDATE_INTERVAL_DAYS} 天）")
        return False

    def download_database(self, force: bool = False) -> bool:
        """
        下载数据库

        Args:
            force: 是否强制重新下载

        Returns:
            是否下载成功
        """
        if not REQUESTS_AVAILABLE:
            logger.error("requests 库未安装，请运行: pip install requests")
            return False

        if not self.check_db_need_update(force):
            return True

        if not self.license_key:
            logger.error("未找到 MaxMind License Key!")
            logger.error("请设置环境变量 MAXMIND_LICENSE_KEY")
            logger.error("或访问 https://dev.maxmind.com/geoip/geolite2-free-geolocation-data 注册获取免费密钥")
            return False

        # 确保数据目录存在
        os.makedirs(self.db_dir, exist_ok=True)

        logger.info("开始下载 GeoLite2 数据库...")

        # 构建下载URL
        params = {
            'edition_id': GEOLITE_EDITION_ID,
            'license_key': self.license_key,
            'suffix': GEOLITE_SUFFIX
        }

        try:
            # 下载压缩包
            response = requests.get(
                GEOLITE_URL,
                params=params,
                stream=True,
                timeout=300
            )
            response.raise_for_status()

            # 获取文件名
            content_disposition = response.headers.get('Content-Disposition', '')
            filename = ''
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[-1].strip('"')

            if not filename:
                filename = f"{GEOLITE_EDITION_ID}.{GEOLITE_SUFFIX}"

            logger.info(f"下载文件: {filename}")

            # 下载到临时文件
            with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz') as tmp_file:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0

                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        tmp_file.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"\r下载进度: {progress:.1f}%", end='', flush=True)

                print()  # 换行
                tmp_file_path = tmp_file.name

            logger.info("下载完成，正在解压...")

            # 解压文件
            with tempfile.TemporaryDirectory() as tmp_dir:
                # 解压 tar.gz
                with tarfile.open(tmp_file_path, 'r:gz') as tar:
                    tar.extractall(tmp_dir)

                # 查找 .mmdb 文件
                mmdb_files = list(Path(tmp_dir).rglob('*.mmdb'))

                if not mmdb_files:
                    logger.error("在下载的文件中未找到 .mmdb 数据库文件")
                    os.unlink(tmp_file_path)
                    return False

                mmdb_file = mmdb_files[0]
                logger.info(f"找到数据库文件: {mmdb_file}")

                # 备份旧文件
                if os.path.exists(self.db_path):
                    backup_path = self.db_path + '.backup'
                    shutil.copy2(self.db_path, backup_path)
                    logger.info(f"已备份旧数据库到: {backup_path}")

                # 复制新文件
                shutil.copy2(mmdb_file, self.db_path)

                # 清理临时文件
                os.unlink(tmp_file_path)

            # 验证新文件
            file_size = os.path.getsize(self.db_path)
            logger.info(f"数据库安装成功: {self.db_path}")
            logger.info(f"文件大小: {file_size / 1024 / 1024:.2f} MB")

            # 测试读取
            try:
                import geoip2.database
                reader = geoip2.database.Reader(self.db_path)
                logger.info("数据库验证成功，可以正常读取")
                reader.close()
            except Exception as e:
                logger.error(f"数据库验证失败: {e}")
                return False

            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"下载失败: {e}")
            return False
        except tarfile.TarError as e:
            logger.error(f"解压失败: {e}")
            return False
        except Exception as e:
            logger.error(f"安装失败: {e}")
            return False


def load_license_key_from_config() -> str:
    """从配置文件加载 License Key"""
    # 尝试从 .env 文件读取
    env_file = os.path.join(BASE_DIR, '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('MAXMIND_LICENSE_KEY='):
                    key = line.split('=', 1)[1].strip().strip('"\'')
                    if key:
                        return key

    # 尝试从配置文件读取
    try:
        from config import Config
        if hasattr(Config, 'maxmind_license_key') and Config.maxmind_license_key:
            return Config.maxmind_license_key
    except:
        pass

    return None


def main():
    parser = argparse.ArgumentParser(description='GeoLite2 数据库下载工具')
    parser.add_argument('--force', action='store_true', help='强制重新下载')
    parser.add_argument('--check', action='store_true', help='仅检查是否需要更新')
    parser.add_argument('--key', help='MaxMind License Key（可选，优先使用环境变量）')
    parser.add_argument('--account-id', help='MaxMind Account ID（可选）')

    args = parser.parse_args()

    # 获取 License Key
    license_key = args.key or load_license_key_from_config()
    if license_key:
        os.environ['MAXMIND_LICENSE_KEY'] = license_key

    # 创建下载器
    downloader = GeoIPDownloader(
        license_key=license_key,
        account_id=args.account_id
    )

    # 检查模式
    if args.check:
        if downloader.check_db_exists():
            age = downloader.check_db_age()
            print(f"✓ 数据库存在: {downloader.db_path}")
            print(f"  文件年龄: {age} 天")
            print(f"  文件大小: {os.path.getsize(downloader.db_path) / 1024 / 1024:.2f} MB")
            if age >= UPDATE_INTERVAL_DAYS:
                print(f"  状态: 需要更新（超过 {UPDATE_INTERVAL_DAYS} 天）")
                return 1
            else:
                print(f"  状态: 最新（更新周期: {UPDATE_INTERVAL_DAYS} 天）")
                return 0
        else:
            print(f"✗ 数据库不存在: {downloader.db_path}")
            return 1

    # 下载模式
    if downloader.download_database(force=args.force):
        print("\n✓ 数据库下载并安装成功!")
        print(f"  位置: {downloader.db_path}")
        return 0
    else:
        print("\n✗ 数据库下载失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
