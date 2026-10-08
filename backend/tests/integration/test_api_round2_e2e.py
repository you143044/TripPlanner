"""API集成测试 - 第二轮: 完整生成链路与结果校验

提交一个正常请求 → 轮询 → 校验结果JSON结构与数据一致性。
"""

import time
import requests

BASE = "http://localhost:8000"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {name}" + (f"  .. {detail}" if detail else ""))
    (PASS if ok else FAIL).append(name)


print("=" * 60)
print("完整生成链路测试")
print("=" * 60)

payload = {
    "city": "北京",
    "start_date": "2026-10-20",
    "end_date": "2026-10-22",
    "travel_days": 3,
    "transportation": "公共交通",
    "accommodation": "经济型酒店",
    "preferences": ["历史文化", "美食"],
    "free_text_input": "希望多一些博物馆",
}
headers = {"X-User-Id": "e2e-integration-user-001"}

t0 = time.time()
r = requests.post(f"{BASE}/api/trip/plan", json=payload, headers=headers, timeout=10)
ok = r.status_code == 200 and r.json().get("success") and r.json().get("task_id")
check("提交任务返回task_id", ok, f"status={r.status_code}")
if not ok:
    print("ABORT - 提交失败")
    exit(1)
task_id = r.json()["task_id"]
check("初始状态为pending", r.json().get("status") == "pending", f"status={r.json().get('status')}")

# 轮询
final = None
for i in range(90):
    time.sleep(3)
    rr = requests.get(f"{BASE}/api/trip/plan/{task_id}", timeout=10)
    j = rr.json()
    if i % 5 == 0:
        print(f"  poll[{i*3}s] status={j['status']} step={j.get('step_label','')[:20]}")
    if j["status"] in ("success", "failed"):
        final = j
        break

elapsed = time.time() - t0
check("任务进入终态", final is not None, f"elapsed={elapsed:.0f}s")
if not final:
    print("ABORT - 轮询超时")
    exit(1)

check("任务成功", final["status"] == "success", f"status={final['status']} err={final.get('error_message')}")

if final["status"] == "success" and final.get("data"):
    data = final["data"]
    check("success标志", final.get("success") is True)
    check("响应city一致", data["city"] == "北京", f"{data['city']}")
    check("响应start_date一致", data["start_date"] == "2026-10-20", f"{data['start_date']}")
    check("响应end_date一致", data["end_date"] == "2026-10-22", f"{data['end_date']}")
    check("天数=3", len(data["days"]) == 3, f"days={len(data['days'])}")
    check("duration_ms已记录", isinstance(final.get("duration_ms"), int))

    # 每日行程结构
    day0 = data["days"][0]
    check("day0.day_index=0", day0["day_index"] == 0)
    check("day0.date匹配开始日期", day0["date"] == "2026-10-20", f"{day0['date']}")
    check("day0有景点", len(day0["attractions"]) > 0)
    check("day0有3餐", len(day0["meals"]) == 3, f"meals={len(day0['meals'])}")

    # 日期连续性
    dates = [d["date"] for d in data["days"]]
    from datetime import date as D, timedelta
    start = D(2026, 10, 20)
    expected = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(3)]
    check("日期连续且正确", dates == expected, f"{dates}")

    # 坐标合法性
    coords_ok = all(
        abs(a["location"]["longitude"]) <= 180 and abs(a["location"]["latitude"]) <= 90
        for d in data["days"] for a in d["attractions"]
    )
    check("所有景点坐标合法", coords_ok)

    # 历史记录中能看到该任务
    hr = requests.get(f"{BASE}/api/trip/history", params={"limit": 50}, headers=headers, timeout=10)
    items = hr.json().get("items", [])
    check("历史记录含该任务", any(it["task_id"] == task_id for it in items), f"total={hr.json().get('total')}")

print()
print(f"===== 第二轮: {len(PASS)} 通过, {len(FAIL)} 失败 =====")
for f in FAIL:
    print("  FAIL:", f)
raise SystemExit(1 if FAIL else 0)