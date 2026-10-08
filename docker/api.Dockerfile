FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY config/ ./config/
COPY detection/ ./detection/
COPY advisor/ ./advisor/
COPY alerts/ ./alerts/
COPY api/ ./api/
COPY backtest/ ./backtest/
COPY evaluation/ ./evaluation/
COPY jobs/ ./jobs/
COPY processing/ ./processing/
COPY storage/ ./storage/
EXPOSE 8000
CMD ["python", "-m", "api.main"]