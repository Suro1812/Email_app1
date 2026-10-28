FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN python -m pip install --upgrade pip setuptools wheel

COPY pyproject.toml ./
COPY app ./app
COPY frontend ./frontend

RUN pip install --no-cache-dir -e .

COPY scripts ./scripts
RUN chmod +x ./scripts/start-api.sh ./scripts/start-worker.sh

EXPOSE 8000

CMD ["./scripts/start-api.sh"]
