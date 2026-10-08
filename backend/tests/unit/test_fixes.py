"""修复验证测试: 日期校验 / POI address数组 / 天气·路线REST / CORS"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))


class TestTripRequestDateValidation:
    """P1: 日期格式/顺序/天数一致性"""

    def _req(self, **over):
        base = dict(
            city="北京",
            start_date="2026-10-01",
            end_date="2026-10-03",
            travel_days=3,
            transportation="公共交通",
            accommodation="经济型酒店",
        )
        base.update(over)
        from app.models.schemas import TripRequest
        return TripRequest(**base)

    def test_valid_passes(self):
        assert self._req().travel_days == 3

    def test_invalid_date_format_rejected(self):
        from app.models.schemas import TripRequest
        with pytest.raises(ValidationError):
            TripRequest(**dict(
                city="北京", start_date="not-a-date", end_date="2026-10-03",
                travel_days=3, transportation="步行", accommodation="民宿"))

    def test_fake_date_rejected(self):
        """2026-02-30 不存在,必须422"""
        from app.models.schemas import TripRequest
        with pytest.raises(ValidationError):
            TripRequest(**dict(
                city="北京", start_date="2026-02-30", end_date="2026-10-03",
                travel_days=3, transportation="步行", accommodation="民宿"))

    def test_end_before_start_rejected(self):
        with pytest.raises(ValidationError):
            self._req(start_date="2026-10-10")

    def test_days_mismatch_rejected(self):
        """日期区间3天但travel_days=2,必须拒绝"""
        with pytest.raises(ValidationError):
            self._req(travel_days=2)

    def test_blank_city_rejected(self):
        with pytest.raises(ValidationError):
            self._req(city="  ")

    def test_oversized_free_text_rejected(self):
        with pytest.raises(ValidationError):
            self._req(free_text_input="长" * 501)


class TestPoiAddressArrayNormalization:
    """P2: 高德返回 address/tel 为数组时,POI搜索不得整单失败"""

    def test_address_array_normalized(self, monkeypatch):
        import requests
        from app.services import amap_service

        fake_resp = requests.Response()
        fake_resp.status_code = 200
        fake_resp._content = (
            '{"status":"1","info":"OK","pois":['
            '{"id":"1","name":"八达岭长城","address":[],"location":"116.01,40.35","tel":[]},'
            '{"id":"2","name":"故宫","address":"东城区与景山前街交汇处","location":"116.39,39.91","tel":["010-85007421","010-85007422"]}'
            ']}'
        ).encode("utf-8")

        def fake_get(url, params=None, **kw):
            assert "place/text" in url
            return fake_resp

        monkeypatch.setattr(requests, "get", fake_get)
        # 清掉可能命中的缓存
        amap_service._poi_cache.clear()
        amap_service._poi_cache_times.clear()

        service = amap_service.get_amap_service()
        pois = service.search_poi("八达岭长城", "北京")

        assert len(pois) == 2  # address=[] 的条目不再导致整单校验失败
        by_id = {p.id: p for p in pois}
        assert by_id["1"].address == ""          # list -> str(空)
        assert by_id["1"].tel == ""
        assert by_id["2"].address == "东城区与景山前街交汇处"
        assert by_id["2"].tel == "010-85007421,010-85007422"


class TestWeatherRest:
    """P2: /api/map/weather 直连高德REST解析"""

    def test_weather_parsing(self, monkeypatch):
        import requests
        from app.services.amap_service import get_amap_service

        fake = requests.Response()
        fake.status_code = 200
        fake._content = (
            '{"status":"1","info":"OK","forecasts":[{"city":"北京","casts":['
            '{"date":"2026-10-08","dayweather":"晴","nightweather":"多云",'
            '"daytemp":"25","nighttemp":"15","daywind":"南风","daypower":"1-3级"}]}]}'
        ).encode("utf-8")

        def fake_get(url, params=None, **kw):
            assert "weather/weatherInfo" in url
            return fake

        monkeypatch.setattr(requests, "get", fake_get)
        from app.services import amap_service
        amap_service._poi_cache.clear()
        amap_service._poi_cache_times.clear()

        weather = get_amap_service().get_weather("北京")
        assert len(weather) == 1
        assert weather[0].date == "2026-10-08"
        assert weather[0].day_weather == "晴"
        assert weather[0].day_temp == 25


class TestRouteRest:
    """P2: /api/map/route 不再500,返回结构正确"""

    def test_route_walking_success(self, monkeypatch):
        import requests
        from app.services import amap_service

        geocode_body = '{"status":"1","info":"OK","geocodes":[{"location":"116.39,39.91"}]}'
        direction_body = (
            '{"status":"1","info":"OK","route":{"origin":"116.39,39.91","destination":"116.40,39.92",'
            '"paths":[{"distance":1520,"duration":1200,"steps":[{},{}]}]}}'
        )

        class FakeResp:
            status_code = 200
            def __init__(self, body):
                self._body = body
            def raise_for_status(self):
                pass
            def json(self):
                import json
                return json.loads(self._body)

        geocode_count = {"n": 0}

        def fake_get(url, params=None, **kw):
            if "geocode" in url:
                geocode_count["n"] += 1
                return FakeResp(geocode_body)
            if "direction" in url:
                return FakeResp(direction_body)
            raise AssertionError(f"unexpected url: {url}")

        monkeypatch.setattr(requests, "get", fake_get)
        amap_service._poi_cache.clear()
        amap_service._poi_cache_times.clear()

        route = amap_service.get_amap_service().plan_route(
            "北京市东城区东华门街道", "北京市西城区",
            origin_city="北京", destination_city="北京", route_type="walking")

        assert geocode_count["n"] == 2  # 起终点各转一次坐标
        assert route["distance"] == 1520
        assert route["duration"] == 1200
        assert route["route_type"] == "walking"
        assert "步行" in route["description"]

    def test_route_geocode_failure_returns_error(self, monkeypatch):
        import requests
        from app.services import amap_service

        bad = '{"status":"0","info":"NO_RESULT","geocodes":[]}'
        direction_body = '{"status":"1","route":{}}'

        class FakeResp:
            status_code = 200
            def __init__(self, body):
                self._body = body
            def raise_for_status(self):
                pass
            def json(self):
                import json
                return json.loads(self._body)

        def fake_get(url, params=None, **kw):
            if "geocode" in url:
                return FakeResp(bad)
            return FakeResp(direction_body)

        monkeypatch.setattr(requests, "get", fake_get)
        amap_service._poi_cache.clear()
        amap_service._poi_cache_times.clear()

        route = amap_service.get_amap_service().plan_route(
            "不存在的地址xyz", "北京站", route_type="driving")
        assert "error" in route


class TestCors:
    """P2: 127.0.0.1 前端来源可跨域(白名单包含127.0.0.1)"""

    def test_preflight_127_origin_allowed(self):
        from fastapi.testclient import TestClient
        from app.api.main import app
        from app.config import settings

        origins = settings.get_cors_origins_list()
        assert any("127.0.0.1" in o for o in origins), f"CORS白名单缺少127.0.0.1: {origins}"

        with TestClient(app) as client:
            resp = client.options(
                "/api/trip/history",
                headers={
                    "Origin": "http://127.0.0.1:5173",
                    "Access-Control-Request-Method": "GET",
                },
            )
            assert resp.status_code == 200
            acao = resp.headers.get("access-control-allow-origin")
            assert acao == "http://127.0.0.1:5173"


class TestParseMcpResultFix:
    """P3: _parse_mcp_result 不再无条件丢首行(原先2个xfail用例现在应通过)"""

    def test_parse_single_line_json_list(self):
        from app.services.amap_service import _parse_mcp_result
        assert _parse_mcp_result('[{"id":"1"},{"id":"2"}]') == [{"id": "1"}, {"id": "2"}]

    def test_parse_noprefix_pois_dict(self):
        from app.services.amap_service import _parse_mcp_result
        raw = '{"pois": [{"id": "A"}], "status": "1"}'
        assert _parse_mcp_result(raw) == [{"id": "A"}]

    def test_parse_with_tool_prefix_still_works(self):
        from app.services.amap_service import _parse_mcp_result
        raw = "工具 'amap_maps_text_search' 执行结果:\n[{\"id\":\"1\"}]"
        assert _parse_mcp_result(raw) == [{"id": "1"}]