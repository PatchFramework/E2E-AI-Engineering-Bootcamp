FROM apache/airflow:2.9.2-python3.12

USER root

# Install standard system libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# Install dependencies for parsing, layout analysis, extraction, and pgvector
RUN pip install --no-cache-dir \
    pymupdf \
    pydantic \
    pydantic-settings \
    "openai<3.0.0" \
    sqlalchemy \
    psycopg2-binary \
    "pgvector<0.3.0" \
    boto3 \
    aiohttp \
    instructor \
    pytest

