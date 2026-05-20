FROM python:3-alpine

# 安装依赖（requests 用于 HTTP 调用，BeautifulSoup 备选）
RUN pip install --no-cache-dir requests beautifulsoup4

# 搜索脚本
COPY search.py /app/search.py

WORKDIR /app

CMD ["python3", "/app/search.py"]
