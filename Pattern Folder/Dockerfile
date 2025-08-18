# Используем многоэтапную сборку
# Этап сборки
FROM python:3.9-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    iputils-ping \
    net-tools \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем зависимости для сборки (если нужны)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Создаем и активируем виртуальное окружение
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---
# Финальный этап
FROM python:3.9-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем виртуальное окружение из builder
COPY --from=builder /opt/venv /opt/venv

# Копируем только содержимое папки app
COPY ./app ./app

# Устанавливаем переменные окружения
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_ENV=production

# Создаем непривилегированного пользователя
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app

# Переключаемся на непривилегированного пользователя
USER appuser

# Открываем порт
EXPOSE 5000

# Health check (проверка здоровья)
HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:5000/healthz || exit 1

# Запускаем приложение
CMD ["python", "app.py"]