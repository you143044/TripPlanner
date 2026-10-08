"""结构化日志系统 - 基于loguru，控制台+文件双输出，按天滚动"""

import sys
from pathlib import Path

from loguru import logger

from ..config import get_settings


def setup_logger() -> None:
    """初始化日志：控制台 + 文件(按天滚动，保留7天，可压缩)"""
    settings = get_settings()

    # 移除默认handler，避免重复输出
    logger.remove()

    # 控制台 handler
    log_format_console = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        format=log_format_console,
        enqueue=True,  # 线程安全，可跨线程输出
    )

    # 文件 handler(按天滚动)
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_format_file = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        "{process} | {thread} | "
        "{name}:{function}:{line} | {message}"
    )
    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        level=settings.log_level.upper(),
        format=log_format_file,
        rotation="00:00",     # 每天零点滚动
        retention="7 days",   # 保留7天
        compression="gz",     # 压缩历史日志
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )


# 模块导入时自动初始化，保证全项目 logger 可用
setup_logger()


def get_logger():
    """获取全局logger实例(与直接import logger等价，语义化)"""
    return logger