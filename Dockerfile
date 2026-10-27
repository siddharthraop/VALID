FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY valid/ valid/
COPY data/ data/
CMD ["sh", "-c", "exec uvicorn valid.web:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
