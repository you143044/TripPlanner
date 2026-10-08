# HelloAgents 智能旅行助手 🌍✈️

基于 **HelloAgents** 框架构建的多智能体 AI 旅行规划助手。输入目的地、日期与偏好，自动调用高德地图查询真实景点/天气/酒店，由双模型协同生成完整的多日行程，支持计划持久化、历史回看与一键导出。

## ✨ 功能特点

- 🤖 **多智能体协同**：景点搜索 / 天气查询 / 酒店推荐 / 行程规划 四个子 Agent（Flash 快速检索 + Pro 深度规划双模型）
- 🗺️ **高德真实数据**：POI 直连高德 REST（真实经纬度、地址、电话），天气预报、公交/驾车路线规划
- ⏱️ **异步任务模式**：提交后立即返回 `task_id`，服务端限流排队（并发上限可配），前端轮询真实进度（排队序号 + 各阶段状态）
- 💾 **计划持久化**：每次生成完整结果入库（PostgreSQL / SQLite），按用户（浏览器 UUID）区分，历史记录随时回看
- 🖼️ **持久化缓存**：景点图片 URL（后端缓存 + localStorage）与真实坐标落库，历史查看零重复外部调用
- 📱 **完整功能**：每日行程、住宿/交通/餐饮推荐、天气、预算、地图标记、PDF 导出
- 🔒 **安全防护**：敏感词内容审核、LLM 反注入、任务归属校验、提交限流、请求体限制、生产环境关闭 API 文档

## 🏗️ 技术栈

### 后端
- **框架**：FastAPI + HelloAgents（SimpleAgent 多智能体）
- **LLM**：双模型配置（Flash 检索 + Pro 规划，兼容 OpenAI/DeepSeek 等）
- **地图**：高德地图 REST API（POI / 天气 / 地理编码 / 路线）
- **数据库**：SQLAlchemy + PostgreSQL（生产）/ SQLite（本地）
- **日志**：Loguru（按天滚动、保留 7 天、结构化）

### 前端
- Vue 3 + TypeScript + Vite + Ant Design Vue
- 高德地图 JS API（地图标记与路线展示）
- 路由懒加载（按页分包，首屏更快）

## 📁 项目结构

```
helloagents-trip-planner/
├── backend/
│   ├── app/
│   │   ├── agents/          # 多智能体行程规划
│   │   ├── api/routes/      # FastAPI路由(trip/map/poi)
│   │   ├── core/            # 日志、安全(限流/内容审核)
│   │   ├── db/              # 数据库连接与ORM模型
│   │   ├── models/          # Pydantic Schema
│   │   ├── services/        # 高德/LLM/Unsplash/任务调度
│   │   └── config.py        # 配置管理
│   ├── requirements.txt
│   └── .env.example         # 配置模板(占位符)
├── frontend/
│   └── src/
│       ├── views/           # Home / Result / History
│       ├── services/        # API封装
│       └── types/           # TS类型
├── docker-compose.yml       # nginx + FastAPI + PostgreSQL
├── .env.production.example  # 生产配置模板
└── README.md
```

## 🚀 快速开始

### 本地开发（SQLite，零额外依赖）

```bash
# 后端
cd backend
cp .env.example .env            # 填写 LLM_API_KEY / AMAP_API_KEY
pip install -r requirements.txt
python run.py                   # http://localhost:8000

# 前端
cd frontend
cp .env.example .env            # 填写高德 Web 端 JS API Key
npm install
npm run dev                     # http://localhost:5173
```

### 生产部署（Docker Compose + PostgreSQL）

```bash
cp .env.production.example .env.production   # 填入真实密钥,务必修改 POSTGRES_PASSWORD
docker compose up -d --build
```

一键拉起 `nginx(80) + FastAPI(8000) + PostgreSQL(5432)`，日志与数据库使用持久化卷。

## 🔌 API 概览

| 端点 | 说明 |
|------|------|
| `POST /api/trip/plan` | 提交生成任务，返回 `task_id`（限流：每 IP+用户 60s 内 10 次） |
| `GET /api/trip/plan/{task_id}` | 轮询任务状态（仅限本人，防越权） |
| `GET /api/trip/history` | 当前用户的历史生成记录（分页、倒序） |
| `GET /api/map/poi` | 关键词搜索 POI（真实坐标） |
| `GET /api/map/weather` | 城市天气预报 |
| `POST /api/map/route` | 公交/驾车/步行路线规划 |
| `GET /api/poi/photo` | 景点图片（Unsplash，带缓存） |
| `GET /health` | 健康检查 |

生产环境默认关闭 `/docs`（通过 `DOCS_ENABLED` 控制）。

## 🔒 安全设计

- **内容安全**：额外要求输入经敏感词审核，命中直接拒绝（400），不进入 LLM
- **Prompt 注入**：子 Agent 提示词内置反注入规则，用户输入无法改变系统行为
- **越权防护**：任务详情仅创建者可查，他人/匿名一律 404
- **防滥用**：提交接口 IP+用户级限流、请求体大小限制（64KB）
- **信息隐藏**：生产关闭 API 文档，500 错误不泄露内部细节
- **密钥管理**：全部 `.env` 文件 gitignore 排除，仓库仅含占位模板；nginx 隐藏版本号并附加安全响应头

## 📝 使用指南

1. 首页填写目的地、日期、天数、交通/住宿/偏好与额外要求
2. 点击"开始规划我的旅行"→ 排队 → 实时查看各 Agent 工作进度
3. 获得完整行程：每日景点/酒店/三餐/预算、天气、地图标记
4. 生成记录自动保存，顶部"📋 我的历史"随时回看

## 📄 许可证

CC BY-NC-SA 4.0

## 🙏 致谢

- [HelloAgents 框架](https://github.com/jjyaoao/HelloAgents) - 多智能体框架
- [高德地图开放平台](https://lbs.amap.com/) - 地图服务
- [Unsplash](https://unsplash.com/) - 景点图片