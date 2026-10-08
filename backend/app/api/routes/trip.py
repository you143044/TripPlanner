"""旅行规划API路由 - 异步任务模式(限流排队+状态轮询+结果入库)"""

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from ...models.schemas import TripRequest, TaskInfo, TaskDetail
from ...agents.trip_planner_agent import validate_free_text, check_sensitive_content
from ...services.task_manager import get_task_manager
from ...core.security import rate_limit_dependency
from ...core.logger import get_logger

logger = get_logger()

router = APIRouter(prefix="/trip", tags=["旅行规划"])

# 提交接口限流: 每个 IP+用户 每分钟最多10次(防刷)
plan_rate_limit = rate_limit_dependency(limit=10, window_seconds=60, scope="trip_plan")


@router.post(
    "/plan",
    response_model=TaskInfo,
    summary="提交生成旅行计划任务",
    description="创建任务并进入排队队列,返回task_id供轮询。任务完成后结果持久化到数据库。",
    dependencies=[Depends(plan_rate_limit)],
)
async def plan_trip(
    request: TripRequest,
    x_user_id: str = Header(default="anonymous", description="前端localStorage生成的用户标识")
):
    try:
        # 内容安全: 敏感词直接拒绝,不进入LLM
        sensitive_hits = check_sensitive_content(request.free_text_input or "")
        if sensitive_hits:
            logger.warning(f"敏感内容拦截: user={x_user_id[:16]} hits={sensitive_hits}")
            raise HTTPException(
                status_code=400,
                detail="您输入的额外要求包含不当内容,请修改后重试。"
            )

        # 过滤不合理内容
        if request.free_text_input:
            cleaned = validate_free_text(request.free_text_input)
            if not cleaned:
                raise HTTPException(
                    status_code=400,
                    detail="额外的要求包含不合理内容,已被过滤为空,请重新输入有效需求。"
                )
            request.free_text_input = cleaned

        manager = get_task_manager()
        record = manager.submit(request, user_id=x_user_id[:64])

        return TaskInfo(
            success=True,
            task_id=record.id,
            status=record.status,
            message="任务已提交,正在排队或生成...",
            queue_position=record.queue_position,
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("提交任务失败")
        raise HTTPException(status_code=500, detail="服务器内部错误,请稍后重试")


@router.get("/plan/{task_id}", response_model=TaskDetail, summary="查询生成任务状态", description="轮询此接口获取任务进度,成功时返回完整旅行计划(仅限本人任务)")
async def get_task(task_id: str, x_user_id: str = Header(default="anonymous", description="前端localStorage生成的用户标识")):
    manager = get_task_manager()
    task = manager.get_task(task_id, user_id=x_user_id[:64])
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    return TaskDetail(
        success=(task["status"] == "success"),
        task_id=task["task_id"],
        status=task["status"],
        step=task["step"],
        step_label=task["step_label"],
        queue_position=task["queue_position"],
        duration_ms=task["duration_ms"],
        error_message=task["error_message"],
        data=task["result"],
    )


@router.get("/history", summary="查询当前用户的历史生成记录", description="按时间倒序返回该设备/用户的历史旅行计划")
async def get_history(
    limit: int = Query(20, ge=1, le=100, description="每页条数"),
    offset: int = Query(0, ge=0, description="偏移量"),
    x_user_id: str = Header(default="anonymous", description="前端localStorage生成的用户标识"),
):
    if x_user_id == "anonymous":
        return {"success": True, "items": [], "total": 0, "message": "未识别用户"}

    manager = get_task_manager()
    items, total = manager.list_history(user_id=x_user_id[:64], limit=limit, offset=offset)
    return {"success": True, "items": items, "total": total}


@router.get("/health", summary="健康检查")
async def health_check():
    """健康检查(不实例化Agent,避免无故拉起MCP进程)"""
    from ...db.database import SessionLocal
    try:
        from sqlalchemy import text
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "service": "trip-planner",
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"服务不可用: {str(e)}")