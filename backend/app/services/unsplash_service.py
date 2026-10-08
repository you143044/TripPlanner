"""Unsplash图片服务 - 含内存URL缓存(同一景点只请求一次Unsplash)"""

import threading
import time
import requests
from typing import List, Optional
from ..config import get_settings
from ..core.logger import get_logger

logger = get_logger()

# 景点名 -> 图片URL 内存缓存,避免重复消耗Unsplash极低的免费配额(约50次/小时)
_photo_cache: dict = {}
_photo_cache_times: dict = {}
_photo_cache_lock = threading.Lock()
_PHOTO_CACHE_TTL = 7 * 24 * 3600  # 7天

class UnsplashService:
    """Unsplash图片服务类"""
    
    def __init__(self):
        """初始化服务"""
        settings = get_settings()
        self.access_key = settings.unsplash_access_key
        self.base_url = "https://api.unsplash.com"
    
    def search_photos(self, query: str, per_page: int = 5) -> List[dict]:
        """
        搜索图片
        """
        if not self.access_key:
            logger.warning("UNSPLASH_ACCESS_KEY未配置,跳过图片搜索")
            return []
        try:
            url = f"{self.base_url}/search/photos"
            params = {
                "query": query,
                "per_page": per_page,
                "client_id": self.access_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = data.get("results", [])
            
            # 提取图片URL
            photos = []
            for photo in results:
                photos.append({
                    "id": photo.get("id"),
                    "url": photo.get("urls", {}).get("regular"),
                    "thumb": photo.get("urls", {}).get("thumb"),
                    "description": photo.get("description") or photo.get("alt_description"),
                    "photographer": photo.get("user", {}).get("name")
                })
            
            return photos
            
        except Exception as e:
            logger.error(f"Unsplash搜索失败: {str(e)}")
            return []
    
    def get_photo_url(self, query: str) -> Optional[str]:
        """
        获取单张图片URL(带内存缓存: 同一关键词7天内只请求一次Unsplash)
        """
        # 命中缓存
        with _photo_cache_lock:
            cached = _photo_cache.get(query)
            cached_at = _photo_cache_times.get(query, 0)
            if cached is not None and (time.time() - cached_at) < _PHOTO_CACHE_TTL:
                return cached

        photos = self.search_photos(query, per_page=1)
        url = photos[0].get("url") if photos else None

        # 写入缓存(未找到也缓存为空,避免反复打Unsplash)
        with _photo_cache_lock:
            _photo_cache[query] = url
            _photo_cache_times[query] = time.time()

        if url:
            logger.info(f"Unsplash图片缓存: '{query}' -> {url[:60]}...")
        return url


def get_cached_photo_url(query: str) -> Optional[str]:
    """从缓存直接读取图片URL(不发请求,仅供落库回填使用)"""
    with _photo_cache_lock:
        cached = _photo_cache.get(query)
        cached_at = _photo_cache_times.get(query, 0)
        if cached is not None and (time.time() - cached_at) < _PHOTO_CACHE_TTL:
            return cached
        return None


# 全局服务实例
_unsplash_service = None


def get_unsplash_service() -> UnsplashService:
    """获取Unsplash服务实例(单例模式)"""
    global _unsplash_service
    
    if _unsplash_service is None:
        _unsplash_service = UnsplashService()
    
    return _unsplash_service

