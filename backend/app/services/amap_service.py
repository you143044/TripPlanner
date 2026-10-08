"""高德地图服务封装 - 含信号量限流与POI缓存"""

import json
import re
import threading
import time
from typing import List, Dict, Any, Optional
import requests
from hello_agents.tools import MCPTool
from ..config import get_settings
from ..models.schemas import Location, POIInfo, WeatherInfo
from ..core.logger import get_logger

logger = get_logger()

# 全局MCP工具实例
_amap_mcp_tool = None

# 高德API并发信号量: 限制同时对高德地图服务的调用数,
# 防止超出发行key的QPS限制(个人key约3 QPS)
_amap_semaphore = threading.Semaphore(2)

# POI结果缓存: 同一关键词+城市24小时内只调用一次高德
_poi_cache: Dict[str, List[POIInfo]] = {}
_poi_cache_times: Dict[str, float] = {}
_poi_cache_lock = threading.Lock()
_POI_CACHE_TTL = 24 * 3600  # 24小时


def _safe_int(value: Any) -> int:
    """安全转int,失败返回0"""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _fmt_distance(meters: int) -> str:
    """格式化距离: <1000显示米,否则显示公里"""
    if meters >= 1000:
        return f"{meters / 1000:.1f}公里"
    return f"{meters}米"


def _parse_mcp_result(result: str) -> List[Dict[str, Any]]:
    """解析MCP工具返回的字符串,提取POI数据列表"""
    if not result:
        return []

    text = result.strip()

    # 仅当首行确实是工具前缀时才丢弃(修复: 单行JSON/无前缀文本不再被截断)
    first_line = text.split("\n", 1)[0]
    if ("工具" in first_line and "执行结果" in first_line) or first_line.startswith("工具"):
        body = text.split("\n", 1)[1] if "\n" in text else ""
    else:
        body = text

    if not body.strip():
        return []

    # 尝试直接解析为JSON
    try:
        data = json.loads(body.strip())
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # 可能是 {"pois": [...]} 格式
            for key in ("pois", "data", "results"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data]
    except (json.JSONDecodeError, ValueError):
        pass

    # 尝试从文本中提取JSON数组
    json_match = re.search(r'\[.*\]', body, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

    # 尝试提取单个JSON对象
    json_match = re.search(r'\{.*\}', body, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            if isinstance(data, dict):
                for key in ("pois", "data", "results"):
                    if key in data and isinstance(data[key], list):
                        return data[key]
                return [data]
        except (json.JSONDecodeError, ValueError):
            pass

    return []


def _parse_location(location_str: str) -> Optional[Location]:
    """将 "经度,纬度" 字符串转为 Location 对象"""
    if not location_str:
        return None
    parts = location_str.split(",")
    if len(parts) == 2:
        try:
            return Location(
                longitude=float(parts[0]),
                latitude=float(parts[1])
            )
        except (ValueError, TypeError):
            pass
    return None


def get_amap_mcp_tool() -> MCPTool:
    """
    获取高德地图MCP工具实例(单例模式)
    
    Returns:
        MCPTool实例
    """
    global _amap_mcp_tool
    
    if _amap_mcp_tool is None:
        settings = get_settings()
        
        if not settings.amap_api_key:
            raise ValueError("高德地图API Key未配置,请在.env文件中设置AMAP_API_KEY")
        
        # 创建MCP工具
        _amap_mcp_tool = MCPTool(
            name="amap",
            description="高德地图服务,支持POI搜索、路线规划、天气查询等功能",
            server_command=["uvx", "amap-mcp-server"],
            env={"AMAP_MAPS_API_KEY": settings.amap_api_key},
            auto_expand=True  # 自动展开为独立工具
        )
        
        logger.info(f"高德地图MCP工具初始化成功: {len(_amap_mcp_tool._available_tools)}个工具, "
                    f"可用工具: {[t.get('name') for t in (_amap_mcp_tool._available_tools or [])][:8]}")
    
    return _amap_mcp_tool


class AmapService:
    """高德地图服务封装类"""
    
    @staticmethod
    def _normalize_str(value: Any, field: str = "") -> str:
        """高德可能把 tel/address 等字段返回为数组,统一转字符串"""
        if isinstance(value, list):
            return ",".join(str(v) for v in value)
        return str(value or "")

    def __init__(self):
        """初始化服务"""
        self.mcp_tool = get_amap_mcp_tool()
    
    def search_poi(self, keywords: str, city: str, citylimit: bool = True) -> List[POIInfo]:
        """
        搜索POI(直连高德REST API,带24h缓存与信号量限流)

        说明: 当前版本的amap-mcp-server(text_search)会丢弃经纬度字段,
        因此这里绕开MCP直连高德v3/place/text,以获得真实坐标用于地图展示。

        Args:
            keywords: 搜索关键词
            city: 城市
            citylimit: 是否限制在城市范围内

        Returns:
            POI信息列表(含真实经纬度)
        """
        cache_key = f"{keywords}|{city}|{citylimit}"

        # 命中缓存直接返回,避免重复调用高德API
        with _poi_cache_lock:
            cached = _poi_cache.get(cache_key)
            cached_at = _poi_cache_times.get(cache_key, 0)
            if cached is not None and (time.time() - cached_at) < _POI_CACHE_TTL:
                logger.debug(f"POI缓存命中: '{keywords}'/'{city}' -> {len(cached)}条")
                return cached

        settings = get_settings()
        try:
            # 信号量限流: 同一时间最多2个高德调用
            with _amap_semaphore:
                resp = requests.get(
                    "https://restapi.amap.com/v3/place/text",
                    params={
                        "key": settings.amap_api_key,
                        "keywords": keywords,
                        "city": city,
                        "citylimit": "true" if citylimit else "false",
                        "offset": "10",
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != "1":
                logger.warning(f"高德POI搜索失败: {data.get('info') or data.get('infocode')} ({keywords}/{city})")
                return []

            poi_list: List[POIInfo] = []
            for item in data.get("pois", []):
                location = _parse_location(item.get("location", ""))
                if not location:
                    continue
                # 高德可能把 tel/address 返回为数组,统一归一化为字符串,避免整单校验失败
                poi_list.append(POIInfo(
                    id=str(item.get("id", "")),
                    name=self._normalize_str(item.get("name")),
                    type=self._normalize_str(item.get("type")),
                    address=self._normalize_str(item.get("address")),
                    location=location,
                    tel=self._normalize_str(item.get("tel")),
                ))

            logger.info(f"POI搜索: 关键词='{keywords}', 城市='{city}', 结果数={len(poi_list)}")

            # 写入缓存
            with _poi_cache_lock:
                _poi_cache[cache_key] = poi_list
                _poi_cache_times[cache_key] = time.time()

            return poi_list

        except Exception as e:
            logger.error(f"POI搜索失败: {str(e)}")
            return []
    
    def get_weather(self, city: str) -> List[WeatherInfo]:
        """
        查询天气(直连高德REST v3/weather,带24h缓存与信号量限流)

        Args:
            city: 城市名称

        Returns:
            天气信息列表
        """
        cache_key = f"weather|{city}"
        with _poi_cache_lock:
            cached = _poi_cache.get(cache_key)
            cached_at = _poi_cache_times.get(cache_key, 0)
            if cached is not None and (time.time() - cached_at) < _POI_CACHE_TTL:
                logger.debug(f"天气缓存命中: '{city}'")
                return cached

        settings = get_settings()
        try:
            with _amap_semaphore:
                resp = requests.get(
                    "https://restapi.amap.com/v3/weather/weatherInfo",
                    params={
                        "key": settings.amap_api_key,
                        "city": city,
                        "extensions": "all",
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != "1":
                logger.warning(f"高德天气查询失败: {data.get('info') or data.get('infocode')} ({city})")
                return []

            weather_list: List[WeatherInfo] = []
            forecasts = data.get("forecasts", [])
            for fc in forecasts:
                for cast in fc.get("casts", []):
                    weather_list.append(WeatherInfo(
                        date=cast.get("date", ""),
                        day_weather=cast.get("dayweather", ""),
                        night_weather=cast.get("nightweather", ""),
                        day_temp=cast.get("daytemp", 0),
                        night_temp=cast.get("nighttemp", 0),
                        wind_direction=cast.get("daywind", ""),
                        wind_power=cast.get("daypower", ""),
                    ))

            with _poi_cache_lock:
                _poi_cache[cache_key] = weather_list
                _poi_cache_times[cache_key] = time.time()

            logger.info(f"天气查询: 城市='{city}', 结果数={len(weather_list)}")
            return weather_list

        except Exception as e:
            logger.error(f"天气查询失败: {str(e)}")
            return []

    def _geocode_address(self, address: str, city: Optional[str]) -> Optional[Location]:
        """地址转坐标(高德v3/geocode/geo)"""
        settings = get_settings()
        params = {"key": settings.amap_api_key, "address": address}
        if city:
            params["city"] = city
        try:
            with _amap_semaphore:
                resp = requests.get("https://restapi.amap.com/v3/geocode/geo", params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
            if data.get("status") != "1":
                logger.warning(f"地理编码失败: {data.get('info')} ({address})")
                return None
            geocodes = data.get("geocodes", [])
            if not geocodes:
                logger.warning(f"地理编码无结果: {address}")
                return None
            return _parse_location(geocodes[0].get("location", ""))
        except Exception as e:
            logger.error(f"地理编码异常: {address} - {e}")
            return None

    def plan_route(
        self,
        origin_address: str,
        destination_address: str,
        origin_city: Optional[str] = None,
        destination_city: Optional[str] = None,
        route_type: str = "walking"
    ) -> Dict[str, Any]:
        """
        规划路线(直连高德REST: 地址→坐标→方向规划)

        Args:
            origin_address: 起点地址
            destination_address: 终点地址
            origin_city: 起点城市
            destination_city: 终点城市
            route_type: 路线类型 (walking/driving/transit)

        Returns:
            路线信息(失败时返回{"error": ...})
        """
        if route_type not in ("walking", "driving", "transit"):
            return {"error": f"不支持的路线类型: {route_type}"}

        # 1. 地址转坐标
        origin_loc = self._geocode_address(origin_address, origin_city)
        dest_loc = self._geocode_address(destination_address, destination_city)
        if not origin_loc:
            return {"error": f"起点地址无法定位: {origin_address}"}
        if not dest_loc:
            return {"error": f"终点地址无法定位: {destination_address}"}

        origin = f"{origin_loc.longitude},{origin_loc.latitude}"
        destination = f"{dest_loc.longitude},{dest_loc.latitude}"

        # 2. 根据类型调用对应方向API
        endpoints = {
            "walking": "https://restapi.amap.com/v3/direction/walking",
            "driving": "https://restapi.amap.com/v3/direction/driving",
            "transit": "https://restapi.amap.com/v3/direction/transit/integrated",
        }
        params: Dict[str, Any] = {
            "key": get_settings().amap_api_key,
            "origin": origin,
            "destination": destination,
        }
        if origin_city:
            params["city"] = origin_city
        if destination_city:
            params["cityd"] = destination_city

        try:
            with _amap_semaphore:
                resp = requests.get(endpoints[route_type], params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != "1":
                err = data.get("info") or data.get("infocode")
                logger.warning(f"路线规划失败: {err} ({route_type})")
                return {"error": f"路线规划失败: {err}"}

            route = data.get("route", {})
            if route_type == "transit":
                transits = route.get("transits", []) or []
                if not transits:
                    return {"error": "未找到公交方案"}
                first = transits[0]
                duration_s = _safe_int(first.get("duration"))
                distance_m = _safe_int(first.get("distance"))
                buses = len(first.get("segments", []) or [])
                description = f"公交出行,换乘{buses}段,距离{_fmt_distance(distance_m)}"
            else:
                paths = route.get("paths", []) or []
                if not paths:
                    return {"error": "未找到可用路线"}
                first = paths[0]
                duration_s = _safe_int(first.get("duration"))
                distance_m = _safe_int(first.get("distance"))
                steps = len(first.get("steps", []) or [])
                mode = "步行" if route_type == "walking" else "驾车"
                description = f"{mode}出行,共{steps}个路段,距离{_fmt_distance(distance_m)}"

            logger.info(f"路线规划成功: {route_type} {origin_address} -> {destination_address}, "
                        f"距离={distance_m}m 耗时={duration_s}s")
            return {
                "distance": distance_m,
                "duration": duration_s,
                "route_type": route_type,
                "description": description,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"路线规划请求异常: {str(e)}")
            return {"error": f"路线规划请求失败: {str(e)}"}
        except Exception as e:
            logger.error(f"路线规划异常: {str(e)}")
            return {"error": f"路线规划失败: {str(e)}"}
    
    def geocode(self, address: str, city: Optional[str] = None) -> Optional[Location]:
        """
        地理编码(地址转坐标)

        Args:
            address: 地址
            city: 城市

        Returns:
            经纬度坐标
        """
        try:
            arguments = {"address": address}
            if city:
                arguments["city"] = city

            with _amap_semaphore:
                result = self.mcp_tool.run({
                    "action": "call_tool",
                    "tool_name": "maps_geo",
                    "arguments": arguments
                })

            logger.info(f"地理编码结果: {result[:200]}...")

            # TODO: 解析实际的坐标数据
            return None

        except Exception as e:
            logger.error(f"地理编码失败: {str(e)}")
            return None

    def get_poi_detail(self, poi_id: str) -> Dict[str, Any]:
        """
        获取POI详情

        Args:
            poi_id: POI ID

        Returns:
            POI详情信息
        """
        try:
            with _amap_semaphore:
                result = self.mcp_tool.run({
                    "action": "call_tool",
                    "tool_name": "maps_search_detail",
                    "arguments": {
                        "id": poi_id
                    }
                })

            logger.info(f"POI详情结果: {result[:200]}...")

            # 解析结果并提取图片
            import json
            import re

            # 尝试从结果中提取JSON
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data

            return {"raw": result}

        except Exception as e:
            logger.error(f"获取POI详情失败: {str(e)}")
            return {}


# 创建全局服务实例
_amap_service = None


def get_amap_service() -> AmapService:
    """获取高德地图服务实例(单例模式)"""
    global _amap_service
    
    if _amap_service is None:
        _amap_service = AmapService()
    
    return _amap_service

