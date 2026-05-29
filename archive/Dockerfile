FROM python:3.12-slim

WORKDIR /app

# Install DuckDB Python client and CLI
RUN pip install --no-cache-dir duckdb==1.2.1

# Copy ETL source files
COPY etl.py schema.sql ./

# Default environment
ENV ED_LOGS_DIR=/data/logs
ENV ED_DB_PATH=/data/elite.duckdb

# Entrypoint: run ETL and exit
ENTRYPOINT ["python", "/app/etl.py"]
CMD ["--logs-dir", "/data/logs", "--db-path", "/data/elite.duckdb"]
