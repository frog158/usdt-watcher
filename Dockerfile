FROM python:3.13-slim

WORKDIR /app

# Копируем зависимости и устанавливаем
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем скрипт
COPY wallet_monitor.py .

CMD ["python", "wallet_monitor.py"]
