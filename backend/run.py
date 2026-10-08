"""启动脚本(生产模式: 关闭热重载,多进程可选)"""

import uvicorn
from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()

    uvicorn.run(
        "app.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,  # 生产环境debug=False,不热重载
        workers=1,              # 任务管理器为进程内调度,多worker需引入外部队列后再扩展
        log_level=settings.log_level.lower()
    )

