FROM postgres:16

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*

RUN echo "CREATE EXTENSION IF NOT EXISTS vector;" > /docker-entrypoint-initdb.d/00_enable_vector.sql