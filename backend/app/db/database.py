"""数据库连接管理 - SQLAlchemy,兼容SQLite/PostgreSQL"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from ..config import get_settings


class Base(DeclarativeBase):
    """ORM基类"""


settings = get_settings()

# SQLite需要check_same_thread=False以支持多线程访问
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db():
    """FastAPI依赖: 获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """创建所有表(幂等)"""
    from ..db import models  # noqa: F401 确保模型已注册
    Base.metadata.create_all(bind=engine)