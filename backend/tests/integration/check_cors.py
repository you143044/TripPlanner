"""验证 5173(用户原实例)与 CORS 配置"""
import requests

r = requests.get("http://localhost:5173/", timeout=10)
print("5173 index status:", r.status_code, "| has app:", 'id="app"' in r.text)

r2 = requests.get("http://localhost:5173/api/trip/health", timeout=10)
print("5173 proxy api:", r2.status_code, r2.text[:80])

# CORS 检查: 模拟浏览器从不同 origin 请求后端
for origin in ["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173"]:
    resp = requests.get("http://localhost:8000/health", headers={"Origin": origin}, timeout=10)
    print(f"origin={origin} -> ACAO={resp.headers.get('Access-Control-Allow-Origin')}")