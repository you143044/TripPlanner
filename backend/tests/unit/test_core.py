"""单元测试: validate_free_text 有效性过滤、Schema边界、响应解析、fallback计划"""

import sys
import os
from pathlib import Path

import pytest  # noqa: F401  (xfail 标记使用)

# 确保可以 import backend 包
BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))


class TestValidateFreeText:
    """测试 validate_free_text 过滤逻辑"""

    def test_normal_text_unchanged(self):
        from app.agents.trip_planner_agent import validate_free_text
        text = "希望多安排一些博物馆"
        assert validate_free_text(text) == text

    def test_unreasonable_keyword_removed(self):
        from app.agents.trip_planner_agent import validate_free_text
        cleaned = validate_free_text("想要免费的门票")
        assert "免费" not in cleaned
        assert cleaned == "想要的门票"

    def test_multiple_keywords_removed(self):
        from app.agents.trip_planner_agent import validate_free_text
        cleaned = validate_free_text("免费白嫖不要去火星")
        for kw in ["免费", "白嫖", "火星"]:
            assert kw not in cleaned

    def test_all_removed_returns_empty(self):
        from app.agents.trip_planner_agent import validate_free_text
        assert validate_free_text("免费免费") == ""

    def test_empty_and_none(self):
        from app.agents.trip_planner_agent import validate_free_text
        assert validate_free_text("") == ""
        assert validate_free_text(None) is None

    def test_whitespace_collapsed(self):
        from app.agents.trip_planner_agent import validate_free_text
        assert validate_free_text("  多  安排  博物馆  ") == "多 安排 博物馆"

    def test_boundary_keyword_not_over_matched(self):
        """不应误伤正常词汇(如'休闲'含'休'但不在关键词表)"""
        from app.agents.trip_planner_agent import validate_free_text
        assert validate_free_text("休闲放松") == "休闲放松"


class TestSchemaValidation:
    """测试 Pydantic Schema 边界"""

    def test_valid_trip_request(self):
        from app.models.schemas import TripRequest
        req = TripRequest(
            city="北京",
            start_date="2026-10-01",
            end_date="2026-10-03",
            travel_days=3,
            transportation="公共交通",
            accommodation="经济型酒店",
        )
        assert req.travel_days == 3
        assert req.preferences == []

    def test_travel_days_ge_1(self):
        from pydantic import ValidationError
        from app.models.schemas import TripRequest
        try:
            TripRequest(
                city="北京", start_date="2026-10-01", end_date="2026-10-01",
                travel_days=0, transportation="步行", accommodation="民宿",
            )
            assert False, "应当拒绝 travel_days=0"
        except ValidationError:
            pass

    def test_travel_days_le_30(self):
        from pydantic import ValidationError
        from app.models.schemas import TripRequest
        try:
            TripRequest(
                city="北京", start_date="2026-10-01", end_date="2026-11-01",
                travel_days=31, transportation="步行", accommodation="民宿",
            )
            assert False, "应当拒绝 travel_days=31"
        except ValidationError:
            pass

    def test_missing_city_rejected(self):
        from pydantic import ValidationError
        from app.models.schemas import TripRequest
        try:
            TripRequest(
                start_date="2026-10-01", end_date="2026-10-03",
                travel_days=3, transportation="步行", accommodation="民宿",
            )
            assert False, "应当拒绝缺少 city"
        except ValidationError:
            pass

    def test_weather_temp_parse(self):
        from app.models.schemas import WeatherInfo
        w = WeatherInfo(date="2026-10-01", day_temp="25°C", night_temp="18℃")
        assert w.day_temp == 25
        assert w.night_temp == 18

    def test_weather_temp_invalid_falls_back(self):
        from app.models.schemas import WeatherInfo
        w = WeatherInfo(date="2026-10-01", day_temp="未知", night_temp="10")
        assert w.day_temp == 0
        assert w.night_temp == 10


class TestAmapParsing:
    """测试 amap_service 的 MCP 结果解析(纯函数,无网络)
    注: 原2个xfail用例(单行JSON/无前缀dict被截断)已随_parse_mcp_result修复,
    迁移至 test_fixes.py::TestParseMcpResultFix 中验证通过。
    """

    def test_parse_with_tool_prefix(self):
        from app.services.amap_service import _parse_mcp_result
        raw = "工具 'amap_maps_text_search' 执行结果:\n[{\"id\":\"1\"}]"
        assert _parse_mcp_result(raw) == [{"id": "1"}]

    def test_parse_empty(self):
        from app.services.amap_service import _parse_mcp_result
        assert _parse_mcp_result("") == []
        assert _parse_mcp_result(None) == []

    def test_parse_location(self):
        from app.services.amap_service import _parse_location
        loc = _parse_location("116.39,39.91")
        assert loc is not None
        assert abs(loc.longitude - 116.39) < 1e-6
        assert abs(loc.latitude - 39.91) < 1e-6
        assert _parse_location("") is None
        assert _parse_location("abc") is None
        assert _parse_location("1,2,3") is None


class TestFallbackPlan:
    """测试 fallback 计划生成(Agent 失败时的兜底)"""

    def test_fallback_plan_shape(self):
        from app.models.schemas import TripRequest
        from app.agents.trip_planner_agent import MultiAgentTripPlanner
        from datetime import date

        planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)  # 不触发 __init__ 网络
        req = TripRequest(
            city="西安", start_date="2026-10-01", end_date="2026-10-03",
            travel_days=3, transportation="公共交通", accommodation="经济型酒店",
        )
        plan = planner._create_fallback_plan(req)
        assert plan.city == "西安"
        assert len(plan.days) == 3
        assert plan.days[0].day_index == 0
        assert len(plan.days[0].attractions) == 2
        assert len(plan.days[0].meals) == 3
        assert plan.days[0].date == "2026-10-01"
        assert plan.days[2].date == "2026-10-03"


class TestPlannerResponseParsing:
    """测试 plan_trip 返回的 JSON 解析"""

    def _make_planner(self):
        from app.agents.trip_planner_agent import MultiAgentTripPlanner
        return MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)

    def _simplest_plan_json(self):
        return {
            "city": "北京", "start_date": "2026-10-01", "end_date": "2026-10-01",
            "days": [{
                "date": "2026-10-01", "day_index": 0, "description": "第一天",
                "transportation": "步行", "accommodation": "民宿",
                "attractions": [{
                    "name": "故宫", "address": "东城区", "location": {"longitude": 116.39, "latitude": 39.91},
                    "visit_duration": 120, "description": "著名景点"
                }],
                "meals": [{"type": "breakfast", "name": "早餐"}],
            }],
            "overall_suggestions": "建议"
        }

    def test_parse_with_json_fence(self):
        planner = self._make_planner()
        plan = planner._parse_response("```json\n" + __import__("json").dumps(self._simplest_plan_json(), ensure_ascii=False) + "\n```", None)
        assert plan.city == "北京"
        assert plan.days[0].attractions[0].name == "故宫"

    def test_parse_with_double_fence(self):
        planner = self._make_planner()
        plan = planner._parse_response("```json\n" + __import__("json").dumps(self._simplest_plan_json(), ensure_ascii=False) + "\n```\nnote", None)
        # 双 ``` 形式
        assert plan.city == "北京"

    def test_parse_with_global_hotel_distribution(self):
        import json
        planner = self._make_planner()
        data = self._simplest_plan_json()
        data["hotel"] = {"name": "如家", "address": "市中心", "location": {"longitude": 116.0, "latitude": 40.0},
                         "price_range": "200-400元", "rating": "4.3", "distance": "2km", "type": "民宿"}
        plan = planner._parse_response(json.dumps(data, ensure_ascii=False), None)
        assert plan.days[0].hotel is not None
        assert plan.days[0].hotel.name == "如家"

    def test_parse_invalid_returns_fallback(self):
        import json
        planner = self._make_planner()
        req = __import__("app.models.schemas", fromlist=["TripRequest"]).TripRequest(
            city="广州", start_date="2026-10-01", end_date="2026-10-01",
            travel_days=1, transportation="步行", accommodation="民宿",
        )
        plan = planner._parse_response("根本不是JSON", req)
        assert plan.city == "广州"
        assert len(plan.days) == 1