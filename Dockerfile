FROM python:3.13-slim

WORKDIR /app

# Копируем зависимости и устанавливаем
COPY requirements.txt wallet_monitor.py ./
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "wallet_monitor.py"]
