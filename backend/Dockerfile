# Development image. Compose supplies source-code bind mounts for hot reload.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# OCR is opt-in. Local Poppler/Tesseract are present when enabled via .env;
# neither tool is executed on upload or normal text-only processing.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends poppler-utils tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
RUN python -m pip install --no-cache-dir -e .

COPY alembic.ini ./
COPY migrations ./migrations

RUN useradd --create-home --uid 10001 spurel \
    && mkdir -p /app/.spurel/storage \
    && chown -R spurel:spurel /app
USER spurel

EXPOSE 8000
CMD ["uvicorn", "spurel.main:app", "--host", "0.0.0.0", "--port", "8000"]
