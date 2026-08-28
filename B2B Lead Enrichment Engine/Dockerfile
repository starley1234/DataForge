# Production Dockerfile for B2B Lead Enrichment Engine
FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей для сетевых запросов и сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование требований и установка Python-зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода приложения
COPY . .

# Создание непривилегированного пользователя для безопасности
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Переменные окружения по умолчанию
ENV HOST=0.0.0.0
ENV PORT=8080
ENV LOG_LEVEL=INFO
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Запуск ASGI сервера в production-режиме
CMD ["uvicorn", "web_app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
