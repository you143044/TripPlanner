"""数据库ORM模型"""

import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Text, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class TripRecord(Base):
    """用户每次旅行计划的生成记录"""

    __tablename__ = "trip_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # 用户标识(浏览器localStorage生成的UUID,安全体系接入后替换为账号ID)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    # 用户选择的旅行参数
    city: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    start_date: Mapped[str] = mapped_column(String(16), nullable=False)
    end_date: Mapped[str] = mapped_column(String(16), nullable=False)
    travel_days: Mapped[int] = mapped_column(Integer, nullable=False)
    transportation: Mapped[str] = mapped_column(String(32), nullable=False)
    accommodation: Mapped[str] = mapped_column(String(32), nullable=False)
    preferences: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    free_text_input: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # 任务状态: pending(排队中)/processing(生成中)/success(成功)/failed(失败)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False, index=True)
    queue_position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 生成结果(完整TripPlan JSON)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    # 候选生成耗时(秒)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["Base", "TripRecord"]