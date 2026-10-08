"""API集成测试 - 针对运行中的后端(localhost:8000)

覆盖: 基础端点 / CORS安全 / POI搜索 / 图片 / 异常输入 / 历史记录
说明: 部分端点会真实调用外部API(高德REST/Unsplash), 消耗少量配额。
"""

import json
import time
import requests

BASE = "http://localhost:8000"
PASS = []
FAIL = []


def check(name: str, ok: bool, detail: str = ""):
    tag = "✅" if ok else "❌"
    print(f"  {tag} {name}" + (f"  [{detail}]" if detail else ""))
    (PASS if ok else FAIL).append((name, detail))


print("=" * 60)
print("1. 基础端点")
print("=" * 60)

r = requests.get(f"{BASE}/", timeout=10)
check("GET /", r.status_code == 200 and r.json().get("status") == "running", f"status={r.status_code}")

r = requests.get(f"{BASE}/health", timeout=10)
check("GET /health", r.status_code == 200 and r.json().get("status") == "healthy", f"status={r.status_code}")

r = requests.get(f"{BASE}/api/trip/health", timeout=10)
check("GET /api/trip/health", r.status_code == 200, f"status={r.status_code} body={r.text[:100]}")

r = requests.get(f"{BASE}/api/map/health", timeout=10)
check("GET /api/map/health", r.status_code in (200, 503), f"status={r.status_code} body={r.text[:150]}")

print()
print("=" * 60)
print("2. CORS 安全测试")
print("=" * 60)

r = requests.get(f"{BASE}/", headers={"Origin": "http://evil.com"}, timeout=10)
acao = r.headers.get("Access-Control-Allow-Origin")
check("恶意Origin被拒绝", acao is None or "evil.com" not in (acao or ""), f"ACAO={acao}")

r = requests.get(f"{BASE}/", headers={"Origin": "http://localhost:5173"}, timeout=10)
acao = r.headers.get("Access-Control-Allow-Origin")
check("合法Origin放行", acao == "http://localhost:5173", f"ACAO={acao}")

print()
print("=" * 60)
print("3. POI 搜索(真实高德REST)")
print("=" * 60)

r = requests.get(f"{BASE}/api/map/poi", params={"keywords": "故宫", "city": "北京"}, timeout=20)
ok = r.status_code == 200 and r.json().get("success") and r.json().get("data")
check("GET /api/map/poi 故宫/北京", ok, f"status={r.status_code} n={len(r.json().get('data') or []) if ok else r.text[:120]}")

r = requests.get(f"{BASE}/api/poi/search", params={"keywords": "天安门", "city": "北京"}, timeout=20)
ok = r.status_code == 200 and r.json().get("success")
check("GET /api/poi/search 天安门/北京", ok, f"status={r.status_code}")

# 非法参数: 空关键词
r = requests.get(f"{BASE}/api/map/poi", params={"city": "北京"}, timeout=10)
check("缺失keywords返回422", r.status_code == 422, f"status={r.status_code}")

# POI搜索结果字段完整性
if ok and r.json().get("data"):
    first = r.json()["data"][0]
    fields = all(k in first for k in ("id", "name", "type", "address", "location"))
    loc_ok = abs(float(first["location"]["longitude"])) <= 180 and abs(float(first["location"]["latitude"])) <= 90
    check("POI字段完整且经纬度合法", fields and loc_ok, f"loc={first['location']}")

print()
print("=" * 60)
print("4. 图片服务(真实Unsplash, 消耗配额)")
print("=" * 60)

r = requests.get(f"{BASE}/api/poi/photo", params={"name": "故宫"}, timeout=20)
ok = r.status_code == 200 and r.json().get("success")
check("GET /api/poi/photo 故宫", ok, f"status={r.status_code} url={r.json().get('data', {}).get('photo_url', '')[:60] if ok else r.text[:120]}")

# 缓存命中检查: 第二次请求应同样成功
r2 = requests.get(f"{BASE}/api/poi/photo", params={"name": "故宫"}, timeout=20)
check("图片请求幂等(缓存)", r2.status_code == 200, f"status={r2.status_code}")

print()
print("=" * 60)
print("5. 异常输入与过滤")
print("=" * 60)

# 5.1 free_text 含不合理关键词 → 400
payload = {
    "city": "北京", "start_date": "2026-10-10", "end_date": "2026-10-11", "travel_days": 2,
    "transportation": "公共交通", "accommodation": "经济型酒店",
    "preferences": [], "free_text_input": "我想要免费的门票",
}
r = requests.post(f"{BASE}/api/trip/plan", json=payload, timeout=10)
check("free_text含不合理词返回400", r.status_code == 400, f"status={r.status_code} detail={r.json().get('detail', '')[:80]}")

# 5.2 非法日期格式 → 观察行为(应为422或提交后失败)
payload2 = dict(payload, start_date="not-a-date", end_date="2026-10-11", free_text_input="")
r = requests.post(f"{BASE}/api/trip/plan", json=payload2, timeout=10)
check("非法日期被拒绝(422/400)", r.status_code in (400, 422), f"status={r.status_code} body={r.text[:150]}")

# 5.3 travel_days 越界
payload3 = dict(payload, travel_days=0, free_text_input="")
r = requests.post(f"{BASE}/api/trip/plan", json=payload3, timeout=10)
check("travel_days=0 返回422", r.status_code == 422, f"status={r.status_code}")

payload4 = dict(payload, travel_days=31, free_text_input="")
r = requests.post(f"{BASE}/api/trip/plan", json=payload4, timeout=10)
check("travel_days=31 返回422", r.status_code == 422, f"status={r.status_code}")

# 5.4 超长X-User-Id header
r = requests.post(f"{BASE}/api/trip/plan", json=payload, headers={"X-User-Id": "A" * 200}, timeout=10)
check("超长X-User-Id不崩溃", r.status_code in (200, 422), f"status={r.status_code}")

# 5.5 查询不存在的任务 → 404
r = requests.get(f"{BASE}/api/trip/plan/00000000-0000-0000-0000-000000000000", timeout=10)
check("查询不存在任务返回404", r.status_code == 404, f"status={r.status_code}")

print()
print("=" * 60)
print("6. 历史记录接口")
print("=" * 60)

r = requests.get(f"{BASE}/api/trip/history", headers={"X-User-Id": "test-integration-user"}, timeout=10)
check("GET /api/trip/history", r.status_code == 200 and r.json().get("success"), f"status={r.status_code} total={r.json().get('total')}")

r = requests.get(f"{BASE}/api/trip/history", timeout=10)  # 无header → anonymous
check("无header返回空列表", r.status_code == 200 and r.json().get("total") == 0, f"status={r.status_code} body={r.text[:100]}")

r = requests.get(f"{BASE}/api/trip/history?limit=0", timeout=10)
check("limit=0 返回422", r.status_code == 422, f"status={r.status_code}")

r = requests.get(f"{BASE}/api/trip/history?limit=999", timeout=10)
check("limit=999 返回422", r.status_code == 422, f"status={r.status_code}")

print()
print(f"===== 第一轮结果: {len(PASS)} 通过, {len(FAIL)} 失败 =====")
for name, detail in FAIL:
    print(f"  ❌ {name}: {detail}")
