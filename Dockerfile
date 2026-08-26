FROM python:3.12-slim

WORKDIR /app

# System libs Pillow needs to decode/encode JPEGs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -e .

# Persisted at runtime via a volume — see docker-compose.yml.
ENV LANDSCAPE_DATA_DIR=/data
VOLUME ["/data"]

EXPOSE 8000

CMD ["uvicorn", "landscape_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
