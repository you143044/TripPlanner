"""修复回归验证 - 对运行中的服务(localhost:8000)

覆盖本次修复: 日期422 / 敏感词400 / route不再500 / weather有数据 / CORS 127.0.0.1 / 越权404
"""

import requests

BASE = "http://localhost:8000"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  .. {detail}" if detail else ""))
    (PASS if ok else FAIL).append(name)


def base_payload(**over):
    p = {
        "city": "北京", "start_date": "2026-11-01", "end_date": "2026-11-02",
        "travel_days": 2, "transportation": "公共交通", "accommodation": "经济型酒店",
        "preferences": [], "free_text_input": "",
    }
    p.update(over)
    return p


print("1. 日期校验(P1)")
r = requests.post(f"{BASE}/api/trip/plan", json=base_payload(start_date="not-a-date"),
                  headers={"X-User-Id": "fix-1"}, timeout=10)
check("非法日期格式->422", r.status_code == 422, f"status={r.status_code}")

r = requests.post(f"{BASE}/api/trip/plan", json=base_payload(start_date="2026-02-30"),
                  headers={"X-User-Id": "fix-2"}, timeout=10)
check("不存在的日期(2026-02-30)->422", r.status_code == 422, f"status={r.status_code}")

r = requests.post(f"{BASE}/api/trip/plan", json=base_payload(start_date="2026-11-10"),
                  headers={"X-User-Id": "fix-3"}, timeout=10)
check("结束早于开始->422", r.status_code == 422, f"status={r.status_code}")

r = requests.post(f"{BASE}/api/trip/plan", json=base_payload(travel_days=1),
                  headers={"X-User-Id": "fix-4"}, timeout=10)
check("日期区间与travel_days不一致->422", r.status_code == 422, f"status={r.status_code}")

print()
print("2. 敏感词拦截")
r = requests.post(f"{BASE}/api/trip/plan", json=base_payload(free_text_input="去赌场玩几把"),
                  headers={"X-User-Id": "fix-5"}, timeout=10)
check("敏感词->400", r.status_code == 400 and "不当内容" in r.json().get("detail", ""),
      f"status={r.status_code} detail={r.json().get('detail','')[:40]}")

r = requests.post(f"{BASE}/api/trip/plan", json=base_payload(free_text_input="想要免费的门票"),
                  headers={"X-User-Id": "fix-6"}, timeout=10)
check("不合理词被清理后正常提交", r.status_code == 200, f"status={r.status_code}")

print()
print("3. 路线规划(P2, 真实高德REST)")
r = requests.post(f"{BASE}/api/map/route", json={
    "origin_address": "北京市朝阳区阜通东大街6号",
    "destination_address": "北京市海淀区上地十街10号",
    "origin_city": "北京", "destination_city": "北京", "route_type": "walking",
}, timeout=20)
ok = r.status_code == 200
check("步行路线->200且含distance/duration",
      ok and "distance" in r.json().get("data", {}) and "duration" in r.json().get("data", {}),
      f"status={r.status_code} data={str(r.json().get('data'))[:120]}")

r = requests.post(f"{BASE}/api/map/route", json={
    "origin_address": "xyz不存在地址qqqq11", "destination_address": "北京站", "route_type": "driving",
}, timeout=20)
# 注: 高德可能对任意字符串做模糊匹配返回远处坐标, 故此处仅断言"不再是500"(200或422均接受)
check("无法定位地址不再500", r.status_code in (200, 422), f"status={r.status_code} body={r.text[:100]}")

r = requests.post(f"{BASE}/api/map/route", json={
    "origin_address": "北京市朝阳区阜通东大街6号",
    "destination_address": "北京市海淀区上地十街10号",
    "route_type": "teleport",
}, timeout=20)
check("非法路线类型->422", r.status_code == 422, f"status={r.status_code}")

print()
print("4. 天气查询(P2, 真实高德REST)")
r = requests.get(f"{BASE}/api/map/weather", params={"city": "北京"}, timeout=20)
ok = r.status_code == 200 and len(r.json().get("data") or []) > 0
check("天气->200且有数据", ok, f"status={r.status_code} n={len(r.json().get('data') or [])}")

print()
print("5. CORS 127.0.0.1(P2)")
r = requests.options(f"{BASE}/api/trip/history",
                     headers={"Origin": "http://127.0.0.1:5173",
                              "Access-Control-Request-Method": "GET"}, timeout=10)
acao = r.headers.get("Access-Control-Allow-Origin")
check("127.0.0.1:5173 预检放行", acao == "http://127.0.0.1:5173", f"ACAO={acao}")

print()
print("6. 越权与历史")
# 先取一个存在的任务(历史任意一条)
r = requests.get(f"{BASE}/api/trip/history", params={"limit": 1},
                 headers={"X-User-Id": "e2e-integration-user-001"}, timeout=10)
items = r.json().get("items", [])
if items:
    tid = items[0]["task_id"]
    own = requests.get(f"{BASE}/api/trip/plan/{tid}",
                       headers={"X-User-Id": "e2e-integration-user-001"}, timeout=10)
    other = requests.get(f"{BASE}/api/trip/plan/{tid}",
                         headers={"X-User-Id": "someone-else"}, timeout=10)
    check("本人可查任务", own.status_code == 200, f"status={own.status_code}")
    check("他人查询->404(防越权)", other.status_code == 404, f"status={other.status_code}")
else:
    print("  .. 无历史任务可测越权,跳过")

r = requests.get(f"{BASE}/docs", timeout=10)
check("docs已开启(本地配置DOCS_ENABLED=true)", r.status_code == 200, f"status={r.status_code}")

print()
print(f"===== 修复回归: {len(PASS)} 通过, {len(FAIL)} 失败 =====")
for f in FAIL:
    print("  FAIL:", f)
raise SystemExit(1 if FAIL else 0)