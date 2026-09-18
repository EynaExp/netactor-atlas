FROM python:3.11-slim AS backend

WORKDIR /build

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

FROM node:20-slim AS frontend

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ .
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

COPY --from=backend /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=backend /build /app

COPY --from=frontend /build/dist /app/static

RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uvicorn

ENV PYTHONPATH=/app
ENV STATIC_FILES_DIR=/app/static

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]