FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 国内镜像加速: pip 使用阿里云源, uv 运行时拉包同样走镜像
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip config set global.trusted-host mirrors.aliyun.com

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir uv

# uv 运行时安装 MCP 依赖(如 amap-mcp-server)也走阿里云镜像
ENV UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple/

COPY . .

EXPOSE 8000

CMD ["python", "run.py"]