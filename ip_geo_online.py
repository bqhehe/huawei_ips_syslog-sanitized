#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IP地理位置在线查询模块
使用免费的在线API进行IP地理位置查询（备用方案）

优点：无需下载数据库，开箱即用
缺点：需要网络连接，有请求速率限制
"""

import logging
import time
import urllib.request
import urllib.parse
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)

# 从主模块导入国家数据
try:
    from ip_geo_locator import COUNTRY_DATA
except ImportError:
    COUNTRY_DATA = {
        'CN': {'name': '中国', 'flag': '🇨🇳'},
        'US': {'name': '美国', 'flag': '🇺🇸'},
        'RU': {'name': '俄罗斯', 'flag': '🇷🇺'},
        # ... 更多国家
    }


class OnlineGeoIP:
    """在线IP地理位置查询器"""

    def __init__(self):
        """初始化在线查询器"""
        self.cache = {}
        self.cache_ttl = 3600  # 缓存1小时
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 最小请求间隔（秒）

        # API列表（按优先级排序）
        self.apis = [
            self._query_ip_api_co,      # ipapi.co - 推荐
            self._query_ip_api_com,     # ip-api.com
            self._query_ipwhois_app,    # ipwhois.app
        ]

    def _get_cached(self, ip: str) -> Optional[Dict[str, Any]]:
        """从缓存获取数据"""
        if ip in self.cache:
            cached_data, cached_time = self.cache[ip]
            if time.time() - cached_time < self.cache_ttl:
                return cached_data
            else:
                del self.cache[ip]
        return None

    def _set_cache(self, ip: str, data: Dict[str, Any]):
        """设置缓存"""
        self.cache[ip] = (data, time.time())

        # 限制缓存大小
        if len(self.cache) > 1000:
            # 删除最旧的10%
            items = sorted(self.cache.items(), key=lambda x: x[1][1])
            for ip, _ in items[:100]:
                del self.cache[ip]

    def _rate_limit(self):
        """请求速率限制"""
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def _normalize_result(self, api_data: Dict[str, Any], ip: str) -> Dict[str, Any]:
        """
        标准化API返回的数据

        Args:
            api_data: API返回的原始数据
            ip: 查询的IP地址

        Returns:
            标准化的地理位置信息
        """
        result = {
            'ip': ip,
            'country_code': None,
            'country_name': '未知',
            'country_flag': '🌍',
            'city': None,
            'region': None,
            'latitude': None,
            'longitude': None,
            'continent': None,
            'timezone': None,
            'is_proxy': False,
            'isp': None,
            'org': None,
            'asn': None,
            'raw': api_data
        }

        # 尝试从不同格式的API响应中提取数据
        if not api_data:
            return result

        # ipapi.co 格式
        if 'country_code' in api_data:
            result['country_code'] = api_data.get('country_code')
            result['country_name'] = api_data.get('country_name', '未知')
            result['city'] = api_data.get('city')
            result['region'] = api_data.get('region')
            result['latitude'] = api_data.get('latitude')
            result['longitude'] = api_data.get('longitude')
            result['timezone'] = api_data.get('timezone')
            result['isp'] = api_data.get('org')
            result['asn'] = api_data.get('asn')

        # ip-api.com 格式
        elif 'countryCode' in api_data:
            result['country_code'] = api_data.get('countryCode')
            result['country_name'] = api_data.get('country', '未知')
            result['city'] = api_data.get('city')
            result['region'] = api_data.get('regionName')
            result['latitude'] = api_data.get('lat')
            result['longitude'] = api_data.get('lon')
            result['timezone'] = api_data.get('timezone')
            result['isp'] = api_data.get('isp')
            result['org'] = api_data.get('org')
            result['asn'] = api_data.get('as')

        # ipwhois.app 格式
        elif 'country_code' in str(api_data).lower():
            # ipwhois 使用驼峰命名
            for key, value in api_data.items():
                if key.lower() == 'country_code':
                    result['country_code'] = value
                elif key.lower() == 'country':
                    result['country_name'] = value
                elif key.lower() == 'city':
                    result['city'] = value
                elif key.lower() == 'region':
                    result['region'] = value
                elif key.lower() == 'latitude':
                    result['latitude'] = value
                elif key.lower() == 'longitude':
                    result['longitude'] = value
                elif key.lower() == 'timezone':
                    result['timezone'] = value
                elif key.lower() == 'connection':
                    if isinstance(value, dict):
                        result['isp'] = value.get('isp')
                        result['org'] = value.get('org')

        # 添加国旗
        if result['country_code']:
            country_info = COUNTRY_DATA.get(result['country_code'].upper(), {})
            result['country_name'] = country_info.get('name', result['country_name'])
            result['country_flag'] = country_info.get('flag', '🌍')
        else:
            result['country_flag'] = '🌍'

        return result

    def _query_ip_api_co(self, ip: str) -> Optional[Dict[str, Any]]:
        """
        使用 ipapi.co API 查询
        免费额度: 1000次/天, 30000次/月
        """
        url = f"https://ipapi.co/{ip}/json/"
        return self._http_get_json(url)

    def _query_ip_api_com(self, ip: str) -> Optional[Dict[str, Any]]:
        """
        使用 ip-api.com API 查询
        免费额度: 45次/分钟 (HTTP), 500次/天 (批量)
        """
        url = f"http://ip-api.com/json/{ip}?lang=zh-CN"
        return self._http_get_json(url)

    def _query_ipwhois_app(self, ip: str) -> Optional[Dict[str, Any]]:
        """
        使用 ipwhois.app API 查询
        免费额度: 无限制 (但建议合理使用)
        """
        url = f"https://ipwhois.app/json/{ip}"
        return self._http_get_json(url)

    def _http_get_json(self, url: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """
        发送HTTP GET请求获取JSON数据

        Args:
            url: 请求URL
            timeout: 超时时间（秒）

        Returns:
            JSON数据字典，失败返回None
        """
        try:
            if REQUESTS_AVAILABLE:
                response = requests.get(url, timeout=timeout)
                response.raise_for_status()
                return response.json()
            else:
                # 使用标准库
                with urllib.request.urlopen(url, timeout=timeout) as response:
                    data = response.read().decode('utf-8')
                    return json.loads(data)
        except Exception as e:
            logger.debug(f"HTTP请求失败 ({url}): {e}")
            return None

    def lookup(self, ip: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        查询IP的地理位置信息

        Args:
            ip: IP地址
            use_cache: 是否使用缓存

        Returns:
            地理位置信息字典
        """
        # 检查缓存
        if use_cache:
            cached = self._get_cached(ip)
            if cached:
                return cached

        # 速率限制
        self._rate_limit()

        # 尝试各个API
        result = None
        for api_func in self.apis:
            try:
                api_data = api_func(ip)
                if api_data:
                    # 检查是否出错
                    if isinstance(api_data, dict):
                        # ip-api.com 错误响应包含 'status' = 'fail'
                        if api_data.get('status') == 'fail':
                            continue
                        # ipapi.co 错误响应包含 'error'
                        if 'error' in api_data:
                            continue

                    result = self._normalize_result(api_data, ip)
                    break
            except Exception as e:
                logger.debug(f"API查询失败 ({api_func.__name__}): {e}")
                continue

        # 如果所有API都失败，返回默认结果
        if result is None:
            result = {
                'ip': ip,
                'country_code': None,
                'country_name': '未知',
                'country_flag': '❓',
                'city': None,
                'region': None,
                'latitude': None,
                'longitude': None,
                'continent': None,
                'timezone': None,
                'is_proxy': False,
                'isp': None,
                'org': None,
                'asn': None,
                'raw': None
            }

        # 缓存结果
        self._set_cache(ip, result)

        return result

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
            # 在线查询需要添加延迟避免被限制
            time.sleep(0.1)
        return results


# 全局单例
online_geo_ip = OnlineGeoIP()


def get_ip_geo_info_online(ip: str) -> Dict[str, Any]:
    """
    获取IP地理位置信息（在线查询，便捷函数）

    Args:
        ip: IP地址

    Returns:
        地理位置信息字典
    """
    return online_geo_ip.lookup(ip)


def get_ip_display_name_online(ip: str) -> str:
    """
    获取IP显示名称（在线查询，便捷函数）

    Args:
        ip: IP地址

    Returns:
        格式化的显示字符串
    """
    return online_geo_ip.get_display_name(ip)


if __name__ == '__main__':
    # 测试代码
    logging.basicConfig(level=logging.DEBUG)

    test_ips = [
        '8.8.8.8',      # Google DNS (美国)
        '1.1.1.1',      # Cloudflare DNS (美国)
        '114.114.114.114',  # 中国DNS
        '223.5.5.5',    # 阿里DNS
    ]

    print("IP地理位置查询测试 (在线API):")
    print("=" * 60)
    for ip in test_ips:
        info = online_geo_ip.lookup(ip)
        display = online_geo_ip.get_display_name(ip)
        print(f"{ip:20} -> {display}")
        if info['latitude'] and info['longitude']:
            print(f"                     坐标: ({info['latitude']:.4f}, {info['longitude']:.4f})")
        if info['isp']:
            print(f"                     ISP: {info['isp']}")
        print()
        time.sleep(0.5)  # 避免请求过快
