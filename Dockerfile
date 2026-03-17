# API and refresh job. Mount data at /app/data (e.g. docker run -v ./data:/app/data).
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src ./src
RUN pip install --no-cache-dir -e .

COPY dashboard ./dashboard
COPY scripts ./scripts

# mm.* from src, dashboard.* from project root
ENV PYTHONPATH=/app:/app/src
EXPOSE 8000

# Default: run API. Override with: docker compose run --rm refresh python scripts/refresh.py
CMD ["uvicorn", "dashboard.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
