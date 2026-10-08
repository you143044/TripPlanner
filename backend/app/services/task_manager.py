"""旅行计划任务管理器 - 限流排队 + 数据库状态机

请求进入 → 创建 pending 记录 → worker 按并发上限逐条执行
→ 结果(或错误)写回DB → 前端轮询任务状态直至完成。

外部API(高德/LLM)的调用频率通过:
1. 任务级并发上限(max_concurrent_generations) 横向控制
2. 高德调用信号量(_amap_semaphore) 纵向控制
3. POI结果缓存 减少重复调用
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy import select

from ..config import get_settings
from ..core.logger import get_logger
from ..db.database import SessionLocal
from ..db.models import TripRecord
from ..models.schemas import TripRequest

logger = get_logger()

# 进度步骤 -> 中文标签(供前端展示)
STEP_LABELS = {
    "searching_attractions": "🔍 景点搜索专家工作中 (Flash模型)",
    "querying_weather": "🌤️ 天气查询专家工作中 (Flash模型)",
    "searching_hotels": "🏨 酒店推荐专家工作中 (Flash模型)",
    "generating_plan": "📋 行程规划专家深度思考中 (Pro模型)",
    "enriching_coordinates": "🗺️ 正在补全真实经纬度...",
    "done": "✅ 规划完成",
    "error": "❌ 出错了",
}
STEP_ORDER = {
    "": 0,
    "searching_attractions": 1,
    "querying_weather": 2,
    "searching_hotels": 3,
    "generating_plan": 4,
    "enriching_coordinates": 5,
    "done": 6,
    "error": 6,
}


class TripTaskManager:
    """单进程旅行任务调度器(配合DB状态机)"""

    def __init__(self):
        self._settings = get_settings()
        self._max_concurrent = self._settings.max_concurrent_generations
        self._task_timeout = self._settings.task_timeout
        self._running: Dict[str, asyncio.Task] = {}
        # 任务id -> 当前进度步骤(内存态,仅用于实时展示)
        self._steps: Dict[str, str] = {}
        self._lock = asyncio.Lock()
        self._stop = False
        self._worker_task: Optional[asyncio.Task] = None
        self._agent = None

    # ---------- 生命周期 ----------

    def start(self):
        """启动后台worker(由FastAPI startup调用)"""
        if self._worker_task is None:
            self._stop = False
            self._worker_task = asyncio.create_task(self._worker_loop())
            logger.info(f"任务管理器已启动, 并发上限={self._max_concurrent}")

    def stop(self):
        """停止后台worker(由FastAPI shutdown调用)"""
        self._stop = True
        if self._worker_task:
            self._worker_task.cancel()

    def _get_agent(self):
        """惰性获取Agent单例(共享无状态)"""
        if self._agent is None:
            from ..agents.trip_planner_agent import get_trip_planner_agent
            self._agent = get_trip_planner_agent()
        return self._agent

    # ---------- 提交与查询 ----------

    def submit(self, request: TripRequest, user_id: str) -> TripRecord:
        """创建任务记录并写入用户选择日志"""
        with SessionLocal() as db:
            ahead = db.query(TripRecord).filter(
                TripRecord.status.in_(["pending", "processing"])
            ).count()
            record = TripRecord(
                user_id=user_id,
                city=request.city,
                start_date=request.start_date,
                end_date=request.end_date,
                travel_days=request.travel_days,
                transportation=request.transportation,
                accommodation=request.accommodation,
                preferences=request.preferences or [],
                free_text_input=request.free_text_input or "",
                status="pending",
                queue_position=ahead + 1,
            )
            db.add(record)
            db.commit()
            db.refresh(record)

        # 用户选择日志(结构化,可直接grep/分析)
        logger.info(
            f"trip_request|task_id={record.id}|user_id={user_id}"
            f"|city={request.city}|dates={request.start_date}~{request.end_date}"
            f"|travel_days={request.travel_days}|transportation={request.transportation}"
            f"|accommodation={request.accommodation}|preferences={','.join(request.preferences or [])}"
            f"|free_text={request.free_text_input or ''}"
        )
        return record

    def get_task(self, task_id: str, user_id: Optional[str] = None) -> Optional[dict]:
        """查询任务状态(供前端轮询)

        Args:
            task_id: 任务ID
            user_id: 当前用户标识;若提供则校验任务归属,非本人返回None(防越权)
        """
        with SessionLocal() as db:
            record = db.get(TripRecord, task_id)
            if record is None:
                return None
            # 越权防护: 记录不属于该用户时视为不存在
            if user_id and record.user_id != user_id:
                return None

            step = self._steps.get(task_id, "")
            queue_position = None
            if record.status == "pending":
                ahead = db.query(TripRecord).filter(
                    TripRecord.status == "pending",
                    TripRecord.created_at < record.created_at,
                ).count()
                queue_position = ahead + 1

            return {
                "task_id": record.id,
                "status": record.status,
                "step": step,
                "step_label": STEP_LABELS.get(step, ""),
                "queue_position": queue_position,
                "duration_ms": record.duration_ms,
                "error_message": record.error_message,
                "result": record.result_json,
                "created_at": record.created_at.isoformat() if record.created_at else None,
            }

    def list_history(self, user_id: str, limit: int = 20, offset: int = 0) -> tuple[list, int]:
        """查询指定用户的历史生成记录(按时间倒序,不含完整result以减小响应)

        Returns:
            (记录摘要列表, 总条数)
        """
        with SessionLocal() as db:
            total = db.query(TripRecord).filter(
                TripRecord.user_id == user_id
            ).count()
            records = db.query(TripRecord).filter(
                TripRecord.user_id == user_id
            ).order_by(TripRecord.created_at.desc()).offset(offset).limit(limit).all()

        items = []
        for r in records:
            items.append({
                "task_id": r.id,
                "city": r.city,
                "start_date": r.start_date,
                "end_date": r.end_date,
                "travel_days": r.travel_days,
                "transportation": r.transportation,
                "accommodation": r.accommodation,
                "preferences": r.preferences or [],
                "free_text_input": r.free_text_input or "",
                "status": r.status,
                "duration_ms": r.duration_ms,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })
        return items, total

    # ---------- worker ----------

    async def _worker_loop(self):
        """后台循环: 有空闲槽位就领取下一个pending任务"""
        while not self._stop:
            try:
                async with self._lock:
                    running_count = len(self._running)

                if running_count < self._max_concurrent:
                    record = self._claim_next()
                    if record is not None:
                        task = asyncio.create_task(self._process(record.id))
                        async with self._lock:
                            self._running[record.id] = task
                        task.add_done_callback(lambda t, tid=record.id: self._on_done(tid, t))
                        continue  # 立即尝试领取下一个,填满并发槽

                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"worker循环异常: {e}")
                await asyncio.sleep(1)

    def _claim_next(self) -> Optional[TripRecord]:
        """领取最早的pending任务并标记为processing"""
        with SessionLocal() as db:
            record = db.execute(
                select(TripRecord)
                .where(TripRecord.status == "pending")
                .order_by(TripRecord.created_at.asc())
                .limit(1)
            ).scalar_one_or_none()
            if record is None:
                return None
            record.status = "processing"
            record.started_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(record)
            return record

    def _on_done(self, task_id: str, task: asyncio.Task):
        """任务结束清理"""
        async def _cleanup():
            async with self._lock:
                self._running.pop(task_id, None)
            self._steps.pop(task_id, None)
        try:
            _ = task.result()  # 触发可能被吞掉的异常记录
        except Exception as e:
            logger.error(f"任务 {task_id} 异常: {e}")
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_cleanup())
        except RuntimeError:
            pass

    def _backfill_images(self, result_json: dict) -> None:
        """把图片缓存中已存在的URL回填进result_json的景点image_url(零网络请求)"""
        try:
            from .unsplash_service import get_cached_photo_url
            filled = 0
            for day in result_json.get("days", []):
                for attr in day.get("attractions", []):
                    if attr.get("image_url"):
                        continue
                    url = get_cached_photo_url(attr.get("name", ""))
                    if url:
                        attr["image_url"] = url
                        filled += 1
            if filled:
                logger.info(f"图片回填: {filled}个景点已附带图片URL,历史查看无需再请求")
        except Exception as e:
            logger.warning(f"图片回填失败(不影响结果): {e}")

    async def _process(self, task_id: str):
        """执行单个任务: 跑Agent → 写回结果"""
        with SessionLocal() as db:
            record = db.get(TripRecord, task_id)
            request = TripRequest(
                city=record.city,
                start_date=record.start_date,
                end_date=record.end_date,
                travel_days=record.travel_days,
                transportation=record.transportation,
                accommodation=record.accommodation,
                preferences=record.preferences or [],
                free_text_input=record.free_text_input or "",
            )

        def on_step(step: str):
            self._steps[task_id] = step

        start = time.time()
        try:
            agent = self._get_agent()
            # Agent为同步阻塞调用,放入线程池;外层 wait_for 兜底超时
            plan = await asyncio.wait_for(
                asyncio.to_thread(agent.plan_trip, request, on_step),
                timeout=self._task_timeout,
            )
            result_json = plan.model_dump(mode="json")
            # 回填缓存中已有的景点图片URL到结果(不发请求),新记录自带图片,历史查看零外部调用
            self._backfill_images(result_json)
            duration_ms = int((time.time() - start) * 1000)

            with SessionLocal() as db:
                rec = db.get(TripRecord, task_id)
                rec.status = "success"
                rec.result_json = result_json
                rec.duration_ms = duration_ms
                rec.finished_at = datetime.now(timezone.utc)
                db.commit()
            logger.info(f"任务完成: task_id={task_id} city={record.city} 耗时={duration_ms}ms")

        except asyncio.TimeoutError:
            logger.error(f"任务超时: task_id={task_id} 超过{self._task_timeout}s")
            with SessionLocal() as db:
                rec = db.get(TripRecord, task_id)
                rec.status = "failed"
                rec.error_message = f"生成超时(>{self._task_timeout}s),请稍后重试"
                rec.finished_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as e:
            logger.exception(f"任务失败: task_id={task_id} err={e}")
            with SessionLocal() as db:
                rec = db.get(TripRecord, task_id)
                rec.status = "failed"
                rec.error_message = str(e)[:500]
                rec.finished_at = datetime.now(timezone.utc)
                db.commit()


# 全局单例
_task_manager: Optional[TripTaskManager] = None


def get_task_manager() -> TripTaskManager:
    global _task_manager
    if _task_manager is None:
        _task_manager = TripTaskManager()
    return _task_manager