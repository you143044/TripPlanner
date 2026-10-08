"""补充验证: weather/route/poi-detail 端点行为"""
import requests

BASE = "http://localhost:8000"

r = requests.get(f"{BASE}/api/map/weather", params={"city": "北京"}, timeout=15)
print("weather status:", r.status_code)
try:
    j = r.json()
    print("weather body:", str(j)[:220])
    print("weather data type:", type(j.get("data")).__name__, "len:", len(j.get("data") or []))
except Exception as e:
    print("weather non-json:", r.text[:200])

r = requests.post(
    f"{BASE}/api/map/route",
    json={
        "origin_address": "北京市朝阳区阜通东大街6号",
        "destination_address": "北京市海淀区上地十街10号",
        "route_type": "walking",
    },
    timeout=15,
)
print("\nroute status:", r.status_code)
try:
    j = r.json()
    print("route body:", str(j)[:220])
except Exception as e:
    print("route non-json:", r.text[:200])

r = requests.get(f"{BASE}/api/poi/detail/test-id", timeout=15)
print("\npoi/detail status:", r.status_code)
try:
    j = r.json()
    print("poi/detail body:", str(j)[:220])
except Exception as e:
    print("poi/detail non-json:", r.text[:200])