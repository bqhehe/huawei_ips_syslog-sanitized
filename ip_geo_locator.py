#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IP地理位置查询模块
使用 MaxMind GeoLite2 数据库进行IP地理位置查询
"""

import os
import logging
import gzip
import hashlib
import tarfile
import tempfile
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

try:
    import geoip2.database
    import geoip2.errors
    GEOIP_AVAILABLE = True
except ImportError:
    GEOIP_AVAILABLE = False

# 尝试导入在线查询模块
ONLINE_GEO_AVAILABLE = False
try:
    from ip_geo_online import online_geo_ip
    ONLINE_GEO_AVAILABLE = True
except ImportError:
    pass

logger = logging.getLogger(__name__)

# 国家代码到国旗和中文名称的映射
COUNTRY_DATA = {
    'CN': {'name': '中国', 'flag': '🇨🇳'},
    'US': {'name': '美国', 'flag': '🇺🇸'},
    'RU': {'name': '俄罗斯', 'flag': '🇷🇺'},
    'DE': {'name': '德国', 'flag': '🇩🇪'},
    'FR': {'name': '法国', 'flag': '🇫🇷'},
    'GB': {'name': '英国', 'flag': '🇬🇧'},
    'JP': {'name': '日本', 'flag': '🇯🇵'},
    'KR': {'name': '韩国', 'flag': '🇰🇷'},
    'IN': {'name': '印度', 'flag': '🇮🇳'},
    'BR': {'name': '巴西', 'flag': '🇧🇷'},
    'CA': {'name': '加拿大', 'flag': '🇨🇦'},
    'AU': {'name': '澳大利亚', 'flag': '🇦🇺'},
    'SG': {'name': '新加坡', 'flag': '🇸🇬'},
    'HK': {'name': '香港', 'flag': '🇭🇰'},
    'TW': {'name': '台湾', 'flag': '🇹🇼'},
    'VN': {'name': '越南', 'flag': '🇻🇳'},
    'TH': {'name': '泰国', 'flag': '🇹🇭'},
    'ID': {'name': '印度尼西亚', 'flag': '🇮🇩'},
    'MY': {'name': '马来西亚', 'flag': '🇲🇾'},
    'PH': {'name': '菲律宾', 'flag': '🇵🇭'},
    'IT': {'name': '意大利', 'flag': '🇮🇹'},
    'ES': {'name': '西班牙', 'flag': '🇪🇸'},
    'NL': {'name': '荷兰', 'flag': '🇳🇱'},
    'UA': {'name': '乌克兰', 'flag': '🇺🇦'},
    'PL': {'name': '波兰', 'flag': '🇵🇱'},
    'SE': {'name': '瑞典', 'flag': '🇸🇪'},
    'NO': {'name': '挪威', 'flag': '🇳🇴'},
    'FI': {'name': '芬兰', 'flag': '🇫🇮'},
    'DK': {'name': '丹麦', 'flag': '🇩🇰'},
    'CH': {'name': '瑞士', 'flag': '🇨🇭'},
    'AT': {'name': '奥地利', 'flag': '🇦🇹'},
    'BE': {'name': '比利时', 'flag': '🇧🇪'},
    'CZ': {'name': '捷克', 'flag': '🇨🇿'},
    'GR': {'name': '希腊', 'flag': '🇬🇷'},
    'PT': {'name': '葡萄牙', 'flag': '🇵🇹'},
    'IE': {'name': '爱尔兰', 'flag': '🇮🇪'},
    'TR': {'name': '土耳其', 'flag': '🇹🇷'},
    'IL': {'name': '以色列', 'flag': '🇮🇱'},
    'SA': {'name': '沙特阿拉伯', 'flag': '🇸🇦'},
    'AE': {'name': '阿联酋', 'flag': '🇦🇪'},
    'ZA': {'name': '南非', 'flag': '🇿🇦'},
    'EG': {'name': '埃及', 'flag': '🇪🇬'},
    'NG': {'name': '尼日利亚', 'flag': '🇳🇬'},
    'KE': {'name': '肯尼亚', 'flag': '🇰🇪'},
    'MX': {'name': '墨西哥', 'flag': '🇲🇽'},
    'AR': {'name': '阿根廷', 'flag': '🇦🇷'},
    'CL': {'name': '智利', 'flag': '🇨🇱'},
    'CO': {'name': '哥伦比亚', 'flag': '🇨🇴'},
    'PE': {'name': '秘鲁', 'flag': '🇵🇪'},
    'VE': {'name': '委内瑞拉', 'flag': '🇻🇪'},
    'NZ': {'name': '新西兰', 'flag': '🇳🇿'},
    'PK': {'name': '巴基斯坦', 'flag': '🇵🇰'},
    'BD': {'name': '孟加拉国', 'flag': '🇧🇩'},
    'LK': {'name': '斯里兰卡', 'flag': '🇱🇰'},
    'NP': {'name': '尼泊尔', 'flag': '🇳🇵'},
    'MM': {'name': '缅甸', 'flag': '🇲🇲'},
    'KH': {'name': '柬埔寨', 'flag': '🇰🇭'},
    'LA': {'name': '老挝', 'flag': '🇱🇦'},
    'KZ': {'name': '哈萨克斯坦', 'flag': '🇰🇿'},
    'UZ': {'name': '乌兹别克斯坦', 'flag': '🇺🇿'},
    'AF': {'name': '阿富汗', 'flag': '🇦🇫'},
    'IR': {'name': '伊朗', 'flag': '🇮🇷'},
    'IQ': {'name': '伊拉克', 'flag': '🇮🇶'},
    'SY': {'name': '叙利亚', 'flag': '🇸🇾'},
    'JO': {'name': '约旦', 'flag': '🇯🇴'},
    'LB': {'name': '黎巴嫩', 'flag': '🇱🇧'},
    'QA': {'name': '卡塔尔', 'flag': '🇶🇦'},
    'KW': {'name': '科威特', 'flag': '🇰🇼'},
    'OM': {'name': '阿曼', 'flag': '🇴🇲'},
    'YE': {'name': '也门', 'flag': '🇾🇪'},
    'RO': {'name': '罗马尼亚', 'flag': '🇷🇴'},
    'BG': {'name': '保加利亚', 'flag': '🇧🇬'},
    'HU': {'name': '匈牙利', 'flag': '🇭🇺'},
    'SK': {'name': '斯洛伐克', 'flag': '🇸🇰'},
    'SI': {'name': '斯洛文尼亚', 'flag': '🇸🇮'},
    'HR': {'name': '克罗地亚', 'flag': '🇭🇷'},
    'RS': {'name': '塞尔维亚', 'flag': '🇷🇸'},
    'BA': {'name': '波黑', 'flag': '🇧🇦'},
    'MK': {'name': '北马其顿', 'flag': '🇲🇰'},
    'AL': {'name': '阿尔巴尼亚', 'flag': '🇦🇱'},
    'ME': {'name': '黑山', 'flag': '🇲🇪'},
    'XK': {'name': '科索沃', 'flag': '🇽🇰'},
    'BY': {'name': '白俄罗斯', 'flag': '🇧🇾'},
    'MD': {'name': '摩尔多瓦', 'flag': '🇲🇩'},
    'GE': {'name': '格鲁吉亚', 'flag': '🇬🇪'},
    'AM': {'name': '亚美尼亚', 'flag': '🇦🇲'},
    'AZ': {'name': '阿塞拜疆', 'flag': '🇦🇿'},
    'IS': {'name': '冰岛', 'flag': '🇮🇸'},
    'LU': {'name': '卢森堡', 'flag': '🇱🇺'},
    'MC': {'name': '摩纳哥', 'flag': '🇲🇨'},
    'AD': {'name': '安道尔', 'flag': '🇦🇩'},
    'SM': {'name': '圣马力诺', 'flag': '🇸🇲'},
    'VA': {'name': '梵蒂冈', 'flag': '🇻🇦'},
    'MT': {'name': '马耳他', 'flag': '🇲🇹'},
    'CY': {'name': '塞浦路斯', 'flag': '🇨🇾'},
    'LI': {'name': '列支敦士登', 'flag': '🇱🇮'},
    # 更多国家...
}


class IPGeoLocator:
    """IP地理位置查询器"""

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化IP地理位置查询器

        Args:
            db_path: GeoLite2数据库文件路径，默认为 data/GeoLite2-City.mmdb
        """
        self.db_path = db_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'data',
            'GeoLite2-City.mmdb'
        )
        self._reader = None
        self._db_mtime = None
        # 内存缓存，避免重复查询
        self._cache = {}
        self._cache_ttl = 3600  # 缓存1小时

    @property
    def reader(self):
        """延迟加载数据库读取器"""
        if not GEOIP_AVAILABLE:
            return None

        if self._reader is None:
            try:
                self._reader = geoip2.database.Reader(self.db_path)
                self._db_mtime = os.path.getmtime(self.db_path)
                logger.info(f"GeoLite2数据库加载成功: {self.db_path}")
            except FileNotFoundError:
                logger.warning(f"GeoLite2数据库不存在: {self.db_path}")
                logger.info("请运行 'python3 scripts/download_geoip_db.py' 下载数据库")
            except Exception as e:
                logger.error(f"加载GeoLite2数据库失败: {e}")

        return self._reader

    def is_available(self) -> bool:
        """检查GeoIP服务是否可用"""
        return self.reader is not None

    def lookup(self, ip: str) -> Dict[str, Any]:
        """
        查询IP的地理位置信息

        Args:
            ip: IP地址

        Returns:
            包含地理位置信息的字典:
            {
                'country_code': 'CN',           # 国家代码
                'country_name': '中国',          # 国家中文名
                'country_flag': '🇨🇳',          # 国旗emoji
                'city': '北京',                 # 城市名
                'latitude': 39.9042,           # 纬度
                'longitude': 116.4074,         # 经度
                'continent': 'Asia',            # 大洲
                'timezone': 'Asia/Shanghai',    # 时区
                'is_proxy': False,              # 是否是代理/VPN
                'raw': {...}                    # 原始数据
            }
            如果查询失败或IP无效，返回默认值
        """
        import time
        current_time = time.time()

        # 检查缓存
        if ip in self._cache:
            cached_result, cached_time = self._cache[ip]
            if current_time - cached_time < self._cache_ttl:
                return cached_result

        result = {
            'country_code': None,
            'country_name': '未知',
            'country_flag': '❓',
            'city': None,
            'latitude': None,
            'longitude': None,
            'continent': None,
            'timezone': None,
            'is_proxy': False,
            'raw': None
        }

        if not self.reader:
            # 本地数据库不可用，尝试使用在线查询
            if ONLINE_GEO_AVAILABLE:
                logger.debug(f"使用在线API查询IP: {ip}")
                return online_geo_ip.lookup(ip)
            return result

        try:
            response = self.reader.city(ip)

            # 获取国家信息
            country = response.country
            if country and country.iso_code:
                result['country_code'] = country.iso_code
                country_info = COUNTRY_DATA.get(country.iso_code, {})
                result['country_name'] = country_info.get('name', country.name or '未知')
                result['country_flag'] = country_info.get('flag', '🌍')

            # 获取城市信息
            city = response.city
            if city and city.name:
                # 获取城市中文名（如果有）
                result['city'] = city.names.get('zh-CN', city.name) if city.names else city.name

            # 获取地理位置
            location = response.location
            if location:
                result['latitude'] = location.latitude
                result['longitude'] = location.longitude

            # 获取大洲
            continent = response.continent
            if continent:
                result['continent'] = continent.code

            # 获取时区
            if location and location.time_zone:
                result['timezone'] = location.time_zone

            # 检测是否是代理/VPN（基于特征判断）
            # 这里可以接入其他数据库进行更精确的判断
            result['is_proxy'] = self._detect_proxy(ip, response)

            result['raw'] = {
                'country': country.__dict__ if country else None,
                'city': city.__dict__ if city else None,
                'location': location.__dict__ if location else None,
            }

        except geoip2.errors.AddressNotFoundError:
            logger.debug(f"IP地址未找到: {ip}")
        except geoip2.errors.GeoIP2Error as e:
            logger.debug(f"GeoIP查询错误 ({ip}): {e}")
        except ValueError as e:
            logger.debug(f"无效的IP地址 {ip}: {e}")
        except Exception as e:
            logger.error(f"查询IP地理位置时发生错误 ({ip}): {e}")

        # 保存到缓存
        self._cache[ip] = (result, current_time)

        # 限制缓存大小
        if len(self._cache) > 10000:
            # 删除最旧的20%
            items = sorted(self._cache.items(), key=lambda x: x[1][1])
            for ip, _ in items[:2000]:
                del self._cache[ip]

        return result

    def _detect_proxy(self, ip: str, response) -> bool:
        """
        检测IP是否可能是代理/VPN
        这是一个基础实现，可以结合其他数据库增强
        """
        # GeoLite2数据库本身不提供代理检测功能
        # 这里可以接入其他数据库或API进行检测
        # 例如: IPQuality, IPInfo, FraudGuard 等

        # 简单的特征检测
        # 1. 检查是否来自知名的数据中心IP段（需要额外数据）
        # 2. 检查是否使用Hosting/Proxy类型的网络（需要额外数据）

        return False

    def get_display_name(self, ip: str) -> str:
        """
        获取IP的显示名称，格式: 🇨🇳 中国-北京

        Args:
            ip: IP地址

        Returns:
            格式化的显示字符串
        """
        info = self.lookup(ip)

        parts = []
        if info['country_flag']:
            parts.append(info['country_flag'])

        if info['country_name'] and info['country_name'] != '未知':
            parts.append(info['country_name'])

        if info['city']:
            parts.append(info['city'])

        return '-'.join(parts) if parts else '未知'

    def batch_lookup(self, ips: list) -> Dict[str, Dict[str, Any]]:
        """
        批量查询IP的地理位置信息

        Args:
            ips: IP地址列表

        Returns:
            以IP为key的字典，值为地理位置信息
        """
        results = {}
        for ip in ips:
            results[ip] = self.lookup(ip)
        return results

    def close(self):
        """关闭数据库连接"""
        if self._reader:
            self._reader.close()
            self._reader = None

    def __del__(self):
        """析构函数，确保关闭连接"""
        self.close()


# 全局单例
ip_geo_locator = IPGeoLocator()


def get_ip_geo_info(ip: str) -> Dict[str, Any]:
    """
    获取IP地理位置信息（便捷函数）

    Args:
        ip: IP地址

    Returns:
        地理位置信息字典
    """
    return ip_geo_locator.lookup(ip)


def get_ip_display_name(ip: str) -> str:
    """
    获取IP显示名称（便捷函数）

    Args:
        ip: IP地址

    Returns:
        格式化的显示字符串
    """
    return ip_geo_locator.get_display_name(ip)


if __name__ == '__main__':
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)

    test_ips = [
        '8.8.8.8',      # Google DNS (美国)
        '1.1.1.1',      # Cloudflare DNS (美国)
        '114.114.114.114',  # 中国DNS
        '223.5.5.5',    # 阿里DNS
        '127.0.0.1',    # 本地
        '192.168.1.1',  # 内网
        'not-an-ip',    # 无效IP
    ]

    print("IP地理位置查询测试:")
    print("=" * 60)
    for ip in test_ips:
        info = ip_geo_locator.lookup(ip)
        display = ip_geo_locator.get_display_name(ip)
        print(f"{ip:20} -> {display}")
        if info['latitude'] and info['longitude']:
            print(f"                     坐标: ({info['latitude']:.4f}, {info['longitude']:.4f})")
        print()
