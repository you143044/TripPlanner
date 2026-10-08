"""FastAPI主应用"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ..config import get_settings, validate_config, print_config
from ..core.logger import get_logger
from ..core.security import BodySizeLimitMiddleware
from ..db.database import init_db
from ..services.task_manager import get_task_manager
from .routes import trip, poi, map as map_routes

logger = get_logger()

# 获取配置
settings = get_settings()

# 创建FastAPI应用(生产环境关闭文档,避免暴露API结构)
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="基于HelloAgents框架的智能旅行规划助手API",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

# 请求体大小限制(最先注册,最后执行: starlette中间件按注册倒序执行)
app.add_middleware(BodySizeLimitMiddleware, max_size=settings.max_body_size)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(trip.router, prefix="/api")
app.include_router(poi.router, prefix="/api")
app.include_router(map_routes.router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("=" * 60)
    logger.info(f"🚀 {settings.app_name} v{settings.app_version}")
    logger.info("=" * 60)

    # 打印配置信息
    print_config()

    # 验证配置
    try:
        validate_config()
        logger.info("✅ 配置验证通过")
    except ValueError as e:
        logger.error(f"❌ 配置验证失败:\n{e}")
        raise

    # 初始化数据库表
    init_db()
    logger.info(f"✅ 数据库初始化完成: {settings.database_url}")

    # 启动任务管理器(限流排队worker)
    get_task_manager().start()

    logger.info("=" * 60)
    logger.info(f"📚 API文档: http://localhost:8000/docs")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("👋 应用正在关闭...")
    get_task_manager().stop()


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )

