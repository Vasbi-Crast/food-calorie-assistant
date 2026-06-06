FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-backend.txt .
RUN pip install --no-cache-dir -r requirements-backend.txt

COPY backend/ ./

EXPOSE 8000
CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8000"]