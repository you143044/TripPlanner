"""配置管理模块"""

import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

helloagents_env = Path(__file__).parent.parent.parent.parent / "HelloAgents" / ".env"
if helloagents_env.exists():
    load_dotenv(helloagents_env, override=False)


class Settings(BaseSettings):
    """应用配置"""

    app_name: str = "HelloAgents智能旅行助手"
    app_version: str = "1.0.0"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8000

    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"

    amap_api_key: str = ""

    unsplash_access_key: str = ""
    unsplash_secret_key: str = ""

    # LLM 配置: 默认模型(向后兼容)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4"

    # 双模型配置: 快速模型(信息检索) & 专业模型(行程规划)
    llm_flash_model: str = "deepseek-v4-flash"
    llm_pro_model: str = "deepseek-v4-pro"

    log_level: str = "INFO"

    # 日志目录
    log_dir: str = "logs"

    # ===== 安全配置 =====
    # 是否启用接口限流(默认开;本地联调可关闭)
    enable_rate_limit: bool = True
    # 是否启用API文档(/docs),生产建议关闭
    docs_enabled: bool = False
    # 请求体最大字节数(默认64KB)
    max_body_size: int = 64 * 1024

    # 数据库连接 (本地开发默认SQLite;生产环境在.env.production中配置PostgreSQL)
    database_url: str = "sqlite:///./trip_records.db"

    # 并发控制: 同时最多执行的生成任务数
    max_concurrent_generations: int = 8
    # 单个生成任务超时(秒)
    task_timeout: int = 180

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    def get_cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(',')]


settings = Settings()


def get_settings() -> Settings:
    return settings


def validate_config():
    errors = []
    warnings = []

    if not settings.amap_api_key:
        errors.append("AMAP_API_KEY未配置")

    llm_api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not llm_api_key:
        warnings.append("LLM_API_KEY或OPENAI_API_KEY未配置,LLM功能可能无法使用")

    if errors:
        error_msg = "配置错误:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(error_msg)

    if warnings:
        print("\n⚠️  配置警告:")
        for w in warnings:
            print(f"  - {w}")

    return True


def print_config():
    print(f"应用名称: {settings.app_name}")
    print(f"版本: {settings.app_version}")
    print(f"服务器: {settings.host}:{settings.port}")
    print(f"高德地图API Key: {'已配置' if settings.amap_api_key else '未配置'}")

    llm_api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    llm_base_url = os.getenv("LLM_BASE_URL") or settings.openai_base_url
    llm_flash = settings.llm_flash_model
    llm_pro = settings.llm_pro_model

    print(f"LLM API Key: {'已配置' if llm_api_key else '未配置'}")
    print(f"LLM Base URL: {llm_base_url}")
    print(f"LLM Flash Model: {llm_flash}")
    print(f"LLM Pro Model: {llm_pro}")
    print(f"日志级别: {settings.log_level}")
