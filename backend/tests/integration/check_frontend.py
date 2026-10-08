"""验证前端 dev server: HTML渲染 + /api 代理连通"""
import requests

r = requests.get("http://localhost:5174/", timeout=10)
print("index.html status:", r.status_code)
print("has #app div:", 'id="app"' in r.text)
print("has main.ts entry:", "/src/main.ts" in r.text)
if "<title>" in r.text:
    print("title:", r.text[r.text.find("<title>") + 7 : r.text.find("</title>")])

r2 = requests.get("http://localhost:5174/api/trip/health", timeout=10)
print("proxy /api/trip/health:", r2.status_code, r2.text[:100])

r3 = requests.get("http://localhost:5174/health", timeout=10)
print("proxy /health:", r3.status_code, r3.text[:100])

# 检查是否加载了antd与相关模块(粗查)
r4 = requests.get("http://localhost:5174/src/main.ts", timeout=10)
print("main.ts fetch:", r4.status_code, "len:", len(r4.text))