FROM python:3.11-slim

WORKDIR /app

# 安装中文字体，避免 Matplotlib 渲染中文时出现方框。
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "mcp.mcp_server"]

